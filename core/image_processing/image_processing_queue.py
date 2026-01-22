import hashlib
import threading
import queue
import logging
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


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

    def wait_until_done(self):
        self.queue.join()

    def _image_hash(self, image: bytes) -> str:
        return hashlib.sha256(image).hexdigest()


    def enqueue(self, image_content: bytes, image_mime_type: str, image_details: dict = dict()) -> str:
        image_hash = image_details.get('image_hash', 'unknown')
        logger.info(f"Enqueueing image for processing - Hash: {image_hash[:8] if isinstance(image_hash, str) else 'unknown'}..., "
                   f"MIME: {image_mime_type}, Size: {len(image_content)} bytes")
        logger.debug(f"Image details: {image_details}")
        
        task = ImageTask(
            image_content=image_content,
            image_mime_type=image_mime_type,
            image_details=image_details,
        )
        self.tasks[task.task_id] = task
        logger.debug(f"Created task with ID: {task.task_id}")
        self.queue.put(task)
        logger.info(f"Task {task.task_id} added to queue. Queue size: {self.queue.qsize()}")
        return task.task_id


    def get_task(self, task_id: str) -> ImageTask:
        return self.tasks[task_id]

    def _worker_loop(self):
        logger.info("Image processing worker thread started")
        while True:
            logger.debug("Waiting for task from queue...")
            task = self.queue.get()
            image_hash = task.image_details.get('image_hash', 'unknown')
            logger.info(f"Processing task {task.task_id} - Hash: {image_hash[:8] if isinstance(image_hash, str) else 'unknown'}...")
            logger.debug(f"Task details: MIME={task.image_mime_type}, Image size={len(task.image_content)} bytes")
            
            try:
                task.status = TaskStatus.PROCESSING
                logger.debug(f"Task {task.task_id} status changed to PROCESSING")
                logger.info(f"Starting LLM analysis for task {task.task_id}")
                result = self.image_analyzer.analyze_image(task.image_content, task.image_mime_type)
                logger.debug(f"LLM analysis completed for task {task.task_id}, result: {result}")

                task.result = result
                task.status = TaskStatus.DONE
                logger.info(f"Task {task.task_id} completed successfully - Hash: {image_hash[:8] if isinstance(image_hash, str) else 'unknown'}...")

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.ERROR
                logger.error(f"Task {task.task_id} failed with error: {str(e)}")
                logger.debug(f"Error type: {type(e).__name__}, Hash: {image_hash[:8] if isinstance(image_hash, str) else 'unknown'}...")

            finally:
                # ← כאן ה-event
                logger.debug(f"Calling on_task_done callback for task {task.task_id}")
                self.on_task_done(
                    task.task_id,
                    task.status,
                    task.result,
                    task.image_details,
                    task.error,
                )
                logger.debug(f"Task {task.task_id} callback completed")

                self.queue.task_done()
                logger.debug(f"Task {task.task_id} marked as done. Remaining queue size: {self.queue.qsize()}")
