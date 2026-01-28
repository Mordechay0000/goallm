import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum

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


class ImageProcessingQueue:
    def __init__(self, image_analyzer, on_task_done) -> None:
        logger.info("Initializing ImageProcessingQueue")
        self.image_analyzer = image_analyzer
        self.on_task_done = on_task_done
        self.queue = queue.Queue()
        self.tasks = {}
        self.worker = threading.Thread(
            target=self._worker_loop, daemon=True
        )
        logger.debug("Starting worker thread for image processing queue")
        self.worker.start()
        logger.info("ImageProcessingQueue initialized successfully")

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


    def get_task(self, task_id: str) -> ImageTask:
        return self.tasks[task_id]

    def _worker_loop(self):
        logger.info("Image processing worker thread started")
        while True:
            logger.debug("Waiting for task from queue...")
            task = self.queue.get()
            image_hash = task.image_details.get("image_hash", "unknown")
            logger.info(
                "Processing task %s - Hash: %s",
                task.task_id,
                _hash_prefix(image_hash),
            )
            logger.debug(
                "Task details: MIME=%s, Image size=%s bytes",
                task.image_mime_type,
                len(task.image_content),
            )

            try:
                task.status = TaskStatus.PROCESSING
                logger.debug("Task %s status changed to PROCESSING", task.task_id)
                logger.info("Starting image analysis for task %s", task.task_id)
                result = self.image_analyzer.analyze_image(
                    task.image_content, task.image_mime_type
                )
                logger.debug("Analysis completed for task %s, result: %s", task.task_id, result)

                task.result = result
                task.status = TaskStatus.DONE
                logger.info(
                    "Task %s completed successfully - Hash: %s",
                    task.task_id,
                    _hash_prefix(image_hash),
                )

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.ERROR
                logger.error("Task %s failed: %s", task.task_id, e)
                logger.debug(
                    "Error type: %s, Hash: %s",
                    type(e).__name__,
                    _hash_prefix(image_hash),
                )

            finally:
                logger.debug("Calling on_task_done callback for task %s", task.task_id)
                self.on_task_done(
                    task.task_id,
                    task.status,
                    task.result,
                    task.image_details,
                    task.error,
                )
                logger.debug("Task %s callback completed", task.task_id)
                self.queue.task_done()
                logger.debug(
                    "Task %s marked as done. Remaining queue size: %s",
                    task.task_id,
                    self.queue.qsize(),
                )
