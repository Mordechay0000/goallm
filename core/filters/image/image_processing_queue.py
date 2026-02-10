import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from data.constants import (
    DEFAULT_ANALYSIS_TIMEOUT_SECONDS,
    WATCHDOG_INTERVAL_SECONDS,
    DEFAULT_MAX_WORKERS,
)

logger = logging.getLogger(__name__)


def _hash_prefix(h: str) -> str:
    return h[:8] + "..." if isinstance(h, str) and len(h) >= 8 else "unknown"


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


@dataclass
class ImageTask:
    image_content: bytes
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_details: dict = field(default_factory=dict)
    image_mime_type: str = None
    status: TaskStatus = TaskStatus.PENDING
    result: tuple | None = None
    error: str | None = None
    enqueued_at: float = field(default_factory=time.time)
    processing_since: float | None = None
    _callback_done: bool = field(default=False, repr=False)


class ImageProcessingQueue:
    def __init__(
        self,
        image_analyzer,
        on_task_done,
        analysis_timeout_seconds: float = DEFAULT_ANALYSIS_TIMEOUT_SECONDS,
        watchdog_interval_seconds: float = WATCHDOG_INTERVAL_SECONDS,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        logger.info(
            "Initializing ImageProcessingQueue (timeout=%ss, watchdog=%ss, max_workers=%s)",
            analysis_timeout_seconds,
            watchdog_interval_seconds,
            self.max_workers,
        )
        self.image_analyzer = image_analyzer
        self.on_task_done = on_task_done
        self.analysis_timeout_seconds = analysis_timeout_seconds
        self.watchdog_interval_seconds = watchdog_interval_seconds
        self.queue = queue.Queue()
        self.tasks = {}
        self._tasks_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._workers: list[threading.Thread] = []
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"ImageQueueWorker-{i}")
            self._workers.append(t)
        self.watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        logger.debug("Starting %s worker(s) and watchdog for image processing queue", self.max_workers)
        for t in self._workers:
            t.start()
        self.watchdog.start()
        logger.info("ImageProcessingQueue initialized successfully (parallel workers=%s)", self.max_workers)

    def wait_until_done(self) -> None:
        self.queue.join()

    def enqueue(
        self,
        image_content: bytes,
        image_mime_type: str,
        image_details: dict | None = None,
    ) -> str:
        details = image_details or {}
        image_hash = details.get("image_hash", "unknown")
        logger.info(
            "Enqueueing image for processing - Hash: %s, MIME: %s, Size: %s bytes",
            _hash_prefix(image_hash),
            image_mime_type,
            len(image_content),
        )
        logger.debug("Image details: %s", details)

        task = ImageTask(
            image_content=image_content,
            image_mime_type=image_mime_type,
            image_details=details,
        )
        self.tasks[task.task_id] = task
        logger.debug("Created task with ID: %s", task.task_id)
        self.queue.put(task)
        logger.info("Task %s added to queue. Queue size: %s", task.task_id, self.queue.qsize())
        return task.task_id

    def get_task(self, task_id: str) -> ImageTask | None:
        """Return the task for task_id, or None if not found."""
        return self.tasks.get(task_id)

    def _run_analyzer(self, task: ImageTask) -> None:
        """Run analyzer in a thread; set task.result/status/error when done."""
        try:
            result = self.image_analyzer.analyze_image(
                task.image_content, task.image_mime_type
            )
            task.result = result
            task.status = TaskStatus.DONE
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.ERROR

    def _worker_loop(self):
        logger.info("Image processing worker thread started")
        while True:
            logger.debug("Waiting for task from queue...")
            task = self.queue.get()
            image_hash = task.image_details.get("image_hash", "unknown")
            logger.info(
                "Processing task %s - Hash: %s (enqueued %.1fs ago)",
                task.task_id,
                _hash_prefix(image_hash),
                time.time() - task.enqueued_at,
            )
            logger.debug(
                "Task details: MIME=%s, Image size=%s bytes",
                task.image_mime_type,
                len(task.image_content),
            )

            task.status = TaskStatus.PROCESSING
            task.processing_since = time.time()
            logger.debug("Task %s status changed to PROCESSING", task.task_id)
            logger.info(
                "Starting image analysis for task %s (timeout=%ss)",
                task.task_id,
                self.analysis_timeout_seconds,
            )

            analysis_thread = threading.Thread(
                target=self._run_analyzer,
                args=(task,),
                daemon=True,
            )
            analysis_thread.start()
            analysis_thread.join(timeout=self.analysis_timeout_seconds)

            if analysis_thread.is_alive():
                logger.warning(
                    "Task %s analysis timed out after %ss - Hash: %s",
                    task.task_id,
                    self.analysis_timeout_seconds,
                    _hash_prefix(image_hash),
                )
                task.status = TaskStatus.ERROR
                task.error = (
                    f"Analysis timeout ({int(self.analysis_timeout_seconds)}s)"
                )

            with self._tasks_lock:
                callback_done = task._callback_done
                if not callback_done:
                    task._callback_done = True

            if not callback_done:
                logger.debug("Calling on_task_done callback for task %s", task.task_id)
                try:
                    self.on_task_done(
                        task.task_id,
                        task.status,
                        task.result,
                        task.image_details,
                        task.error,
                    )
                    logger.debug("Task %s callback completed", task.task_id)
                except Exception as cb_err:
                    logger.exception(
                        "on_task_done failed for task %s (hash: %s), continuing - %s",
                        task.task_id,
                        _hash_prefix(task.image_details.get("image_hash", "?")),
                        cb_err,
                    )

            self.queue.task_done()
            logger.info(
                "Task %s finished - Status: %s. Queue size: %s",
                task.task_id,
                task.status.value,
                self.queue.qsize(),
            )

    def _watchdog_loop(self):
        """Periodically mark tasks stuck in PROCESSING as ERROR so they are not forgotten."""
        logger.info(
            "Image processing watchdog started (interval=%ss, timeout=%ss)",
            self.watchdog_interval_seconds,
            self.analysis_timeout_seconds,
        )
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=self.watchdog_interval_seconds)
            if self._shutdown.is_set():
                break
            now = time.time()
            to_callback = []
            with self._tasks_lock:
                for task_id, task in list(self.tasks.items()):
                    if task.status != TaskStatus.PROCESSING or not task.processing_since:
                        continue
                    elapsed = now - task.processing_since
                    if elapsed < self.analysis_timeout_seconds:
                        continue
                    if task._callback_done:
                        continue
                    task._callback_done = True
                    task.status = TaskStatus.ERROR
                    task.error = (
                        f"Stuck in processing (watchdog after {int(elapsed)}s)"
                    )
                    to_callback.append(
                        (task_id, task.status, task.result, task.image_details, task.error)
                    )
            for task_id, status, result, details, err in to_callback:
                logger.warning(
                    "Watchdog: marking task %s as ERROR (stuck >%ss) - Hash: %s",
                    task_id,
                    int(self.analysis_timeout_seconds),
                    _hash_prefix(details.get("image_hash", "?")),
                )
                try:
                    self.on_task_done(task_id, status, result, details, err)
                except Exception as cb_err:
                    logger.exception(
                        "Watchdog on_task_done failed for task %s - %s",
                        task_id,
                        cb_err,
                    )
