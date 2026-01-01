import base64
import json
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
import uuid
import requests

app = FastAPI()

LLAMA_ENDPOINT = "http://localhost:9090/v1/chat/completions"
MODEL_NAME = "Qwen3VL-8B-Instruct-Q8_0.gguf"
SYSTEM_PROMPT = open("../system_prompt.txt", "r", encoding="utf-8").read()

@app.get("/")
def index():
    # Serve the HTML file when accessing /
    return FileResponse("index.html", media_type="text/html")


def call_llm(image_bytes: bytes, system_prompt: str) -> dict:
    image_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                    }
                ]
            }
        ],
        "temperature": 0.0
    }

    r = requests.post(LLAMA_ENDPOINT, json=payload, timeout=60)
    r.raise_for_status()
    
    # הסתכל על המבנה של ה‑response של השרת שלך (ייתכן שתצטרך להתאים את הפענוח)
    content = json.loads(r.json()["choices"][0]["message"]["content"])
    print("LLM Response Content:", content)
    return content


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

    result = call_llm(image_bytes, SYSTEM_PROMPT)


    return result
