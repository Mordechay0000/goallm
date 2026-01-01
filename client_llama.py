import base64
import requests
import json

LLAMA_ENDPOINT = "http://localhost:9090/v1/chat/completions"
MODEL_NAME = "Qwen3VL-8B-Thinking-Q8_0.gguf"

SYSTEM_PROMPT = open("system_prompt.txt", "r", encoding="utf-8").read()

def classify_image_with_llm(image_bytes: bytes) -> dict:
    image_b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0
    }

    r = requests.post(LLAMA_ENDPOINT, json=payload, timeout=60)
    r.raise_for_status()

    content = r.json()["choices"][0]["message"]["content"]

    try:
        data = json.loads(content)
        conditions = data.get("conditions", {})
        if not isinstance(conditions, dict):
            raise ValueError()
    except Exception:
        # fail-closed: אם משהו מוזר – נחשב כאילו כל התנאים true
        return {
            "female_visible_9_plus": True,
            "female_3_to_9_partial_clothing": True,
            "female_under_3_minimal_clothing": True,
            "male_exposed_or_bathing": True,
            "any_body_exposure": True
        }

    return conditions
