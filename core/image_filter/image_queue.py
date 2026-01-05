from asyncio import Task
from email.mime import image
import hashlib
import threading
import queue
import time
from dataclasses import dataclass, field
from enum import Enum
import uuid
import queue
import threading

import threading
from dataclasses import dataclass, field
from enum import Enum
import uuid


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
    def __init__(self, filter_image, on_task_done) -> None:
        self.filter_image = filter_image
        self.on_task_done = on_task_done
        self.queue = queue.Queue()
        self.tasks = {}
        self.worker = threading.Thread(
            target=self._worker_loop, daemon=True
        )
        self.worker.start()

    def wait_until_done(self):
        self.queue.join()

    def _image_hash(self, image: bytes) -> str:
        return hashlib.sha256(image).hexdigest()


    def enqueue(self, image_content: bytes, image_mime_type: str, image_details: dict = dict()) -> str:
        task = ImageTask(
            image_content=image_content,
            image_mime_type=image_mime_type,
            image_details=image_details,
        )
        self.tasks[task.task_id] = task
        self.queue.put(task)
        return task.task_id


    def get_task(self, task_id: str) -> ImageTask:
        return self.tasks[task_id]

    def _worker_loop(self):
        while True:
            task = self.queue.get()
            try:
                task.status = TaskStatus.PROCESSING
                result = self.filter_image.analyze_image(task.image_content, task.image_mime_type)

                task.result = result
                task.status = TaskStatus.DONE

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.ERROR

            finally:
                # ← כאן ה-event
                self.on_task_done(
                    task.task_id,
                    task.status,
                    task.result,
                    task.image_details,
                    task.error,
                )

                self.queue.task_done()