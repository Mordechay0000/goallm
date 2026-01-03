import base64
import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import uuid
import requests

from core.image_filter.filter_image import FilterImage
import core.image_filter.image_queue as image_queue

app = FastAPI()

TASK_RESULTS = {}

def on_task_update(task_id, status, result=None, error=None):
    short_id = task_id[:8]

    if status == image_queue.TaskStatus.PROCESSING:
        print(f"[CALLBACK] {short_id} started")

    elif status == image_queue.TaskStatus.DONE:
        print(f"[CALLBACK] {result}")
        TASK_RESULTS[task_id] = {
            "status": "done",
            "result": result
        }

    elif status == image_queue.TaskStatus.ERROR:
        TASK_RESULTS[task_id] = {
            "status": "error",
            "error": str(error)
        }


QUEUE = image_queue.ImageProcessingQueue(
        FilterImage(),
        on_task_done=on_task_update
    )

@app.get("/")
def index():
    # Serve the HTML file when accessing /
    return FileResponse("test_image_filter/index.html", media_type="text/html")



@app.post("/analyze")
async def analyze_image(
    image: UploadFile = File(None),
    image_url: str = Form(None)
):
    if not image and not image_url:
        return JSONResponse(
            status_code=400,
            content={"error": "No image provided"}
        )

    if image:
        image_bytes = await image.read()
    else:
        image_bytes = requests.get(image_url).content

    task_id = QUEUE.enqueue(image_bytes)

    return task_id


@app.get("/result/{task_id}")
def get_result(task_id: str):
    data = TASK_RESULTS.get(task_id)
    if not data:
        return {"status": "pending"}
    return data


@app.delete("/result/{task_id}")
def delete_result(task_id: str):
    TASK_RESULTS.pop(task_id, None)
    return {"status": "deleted"}
