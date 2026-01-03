from asyncio import Task
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
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    result: tuple | None = None
    error: str | None = None



import queue
import threading


class ImageProcessingQueue:
    def __init__(self, filter_image, on_task_done):
        self.filter = filter_image
        self.on_task_done = on_task_done
        self.queue = queue.Queue()
        self.tasks = {}
        self.worker = threading.Thread(
            target=self._worker_loop, daemon=True
        )
        self.worker.start()

    def wait_until_done(self):
        self.queue.join()


    def enqueue(self, image: str|bytes) -> str:
        task = ImageTask(image=image)
        self.tasks[task.id] = task
        self.queue.put(task)
        return task.id
    

    def get_task(self, task_id: str) -> ImageTask:
        return self.tasks[task_id]

    def _worker_loop(self):
        while True:
            task = self.queue.get()
            try:
                task.status = TaskStatus.PROCESSING
                result = self.filter.analyze_image(task.image)

                task.result = result
                task.status = TaskStatus.DONE

            except Exception as e:
                task.error = str(e)
                task.status = TaskStatus.ERROR

            finally:
                # ← כאן ה-event
                self.on_task_done(
                    task.id,
                    task.status,
                    task.result,
                    task.error,
                )

                self.queue.task_done()