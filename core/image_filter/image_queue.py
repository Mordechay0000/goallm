from asyncio import Task
from email.mime import image
import hashlib
import threading
import queue
import time
from dataclasses import dataclass, field
from enum import Enum
import uuid

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
    image: bytes
    image_hash: str
    image_mime_type: str = None
    status: TaskStatus = TaskStatus.PENDING
    result: tuple | None = None
    error: str | None = None



import queue
import threading


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


    def enqueue(self, image: bytes, image_hash: str = None, image_mime_type: str = "application/octet-stream") -> str:
        if image_hash is None:
            image_hash = self._image_hash(image)
        if image_hash in self.tasks:
            return image_hash

        task = ImageTask(
            image=image,
            image_mime_type=image_mime_type,
            image_hash=image_hash,
        )
        self.tasks[image_hash] = task
        self.queue.put(task)
        return task.image_hash


    def get_task(self, image_hash: str) -> ImageTask:
        return self.tasks[image_hash]

    def _worker_loop(self):
        while True:
            task = self.queue.get()
            try:
                task.status = TaskStatus.PROCESSING
                result = self.filter_image.analyze_image(task.image, task.image_mime_type)

                task.result = result
                task.status = TaskStatus.DONE

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.ERROR

            finally:
                # ← כאן ה-event
                self.on_task_done(
                    task.image_hash,
                    task.status,
                    task.result,
                    task.error,
                )

                self.queue.task_done()