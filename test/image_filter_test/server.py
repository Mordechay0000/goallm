import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import uuid
import magic
import requests

from core.filters.image.image_processing_queue import ImageProcessingQueue, TaskStatus

# Use SimulatedImageAnalyzer when USE_SIMULATED_ANALYZER=1 (no LLM model needed)
if os.environ.get("USE_SIMULATED_ANALYZER"):
    from core.filters.image.simulated_image_analyzer import SimulatedImageAnalyzer
    _ANALYZER = SimulatedImageAnalyzer()
    print("[server] Using SimulatedImageAnalyzer (no LLM)")
else:
    from core.filters.image.llm_image_analyzer import LLMImageAnalyzer
    _ANALYZER = LLMImageAnalyzer()
    print("[server] Using LLMImageAnalyzer")

app = FastAPI()

TASK_RESULTS = {}

def on_task_update(task_id, status, result=None, image_details=None, error=None):
    short_id = task_id[:8]

    if status == TaskStatus.PROCESSING:
        print(f"[CALLBACK] {short_id} started")

    elif status == TaskStatus.DONE:
        # Only send allowed/blocked to frontend – no condition details
        has_yes = any(v == "Yes" for v in (result or {}).values())
        decision = "blocked" if has_yes else "allowed"
        print(f"[CALLBACK] {short_id} -> {decision}")
        TASK_RESULTS[task_id] = {
            "status": "done",
            "result": decision
        }

    elif status == TaskStatus.ERROR:
        TASK_RESULTS[task_id] = {
            "status": "error",
            "error": str(error)
        }


QUEUE = ImageProcessingQueue(
        _ANALYZER,
        on_task_done=on_task_update
    )

_THIS_DIR = Path(__file__).resolve().parent

@app.get("/")
def index():
    # Serve the HTML file when accessing /
    html_path = _THIS_DIR / "index.html"
    return FileResponse(html_path, media_type="text/html")

def detect_image_mime(data: bytes) -> str | None:
    """זיהוי סוג MIME של תמונה מבוסס על חתימה בינארית."""
    head = data[:256].lstrip().lower()
    if (
        head.startswith(b'<svg')
        or (head.startswith(b'<?xml') and b'<svg' in head)
        or b'xmlns="http://www.w3.org/2000/svg"' in head
    ):
        return "image/svg+xml"
    elif data.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"

    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"

    elif data.startswith(b'GIF8'):
        return "image/gif"

    elif data.startswith(b'BM'):
        return "image/bmp"

    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return "image/webp"

    elif data.startswith(b'\x00\x00\x01\x00'):
        return "image/x-icon"

    elif data.startswith((b'II*\x00', b'MM\x00*')):
        return "image/tiff"

    # fallback – only if everything above failed
    elif data:
        try:
            return magic.from_buffer(data, mime=True)
        except Exception:
            return "application/octet-stream"

    return "application/octet-stream"


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

    task_id = QUEUE.enqueue(image_content=image_bytes, image_mime_type=detect_image_mime(image_bytes))

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
