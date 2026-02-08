import base64
import binascii
import json
import logging
from pathlib import Path

import cairosvg
import magic
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler

from core.filters.image.analyzers.base import ImageAnalyzer

logger = logging.getLogger(__name__)

# Project root (core/filters/image/ -> 4 levels up)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class ResponseValidationError(Exception):
    def __init__(
        self,
        *,
        message: dict | None = None,
        raw_response: str | None = None,
        parsed_response: dict | None = None,
    ):
        super().__init__()
        self.message = message
        self.raw_response = raw_response
        self.parsed_response = parsed_response

    def __str__(self):
        parts = [self.__class__.__name__]
        if self.message:
            parts.append(f"message={self.message}")
        return " | ".join(parts)

    def to_dict(self):
        return {
            "error": self.message,
            "message": self.message,
            "raw_response": self.raw_response,
            "parsed_response": self.parsed_response,
        }


class LLMImageAnalyzer(ImageAnalyzer):
    CONDITIONS_CHECK = (
        "female_visible_9_plus",
        "female_3_to_9_partial_clothing",
        "female_under_3_minimal_clothing",
        "boys_teens_men_exposed_or_bathing",
        "any_visible_body_exposure"
    )

    def __init__(self):
        logger.info("Initializing LLMImageAnalyzer")
        system_prompt_path = _PROJECT_ROOT / "config" / "llm" / "system_prompt.txt"
        model_path = _PROJECT_ROOT / "models" / "Qwen3VL-8B-Instruct-Q4_k_m.gguf"
        mmproj_path = _PROJECT_ROOT / "models" / "qwen3_vl_8B_Q8" / "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"

        try:
            logger.debug("Loading system prompt from %s", system_prompt_path)
            with open(system_prompt_path, "r", encoding="utf-8") as f:
                self.SYSTEM_PROMPT = f.read()
            logger.debug("System prompt loaded, length: %s characters", len(self.SYSTEM_PROMPT))
        except FileNotFoundError:
            logger.error("System prompt file not found")
            raise FileNotFoundError(
                f"System prompt file not found: {system_prompt_path}"
            )

        logger.debug("Checking model files - Main: %s, MMProj: %s", model_path, mmproj_path)
        if not model_path.exists():
            logger.error("Model file not found: %s", model_path)
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                "Please ensure the model file exists in the models/ directory."
            )
        if not mmproj_path.exists():
            logger.error("MMProj model file not found: %s", mmproj_path)
            raise FileNotFoundError(
                f"MMProj model file not found: {mmproj_path}. "
                "Please ensure the mmproj model file exists in the models/ directory."
            )
        logger.info("Model files found, loading LLM model...")

        self.llm = Llama(
            model_path=str(model_path),
            chat_handler=Qwen3VLChatHandler(clip_model_path=str(mmproj_path)),
            n_gpu_layers=-1,
            n_ctx=10240,
            swa_full=False,
        )
        logger.info("LLMImageAnalyzer initialized successfully")

    def _svg_to_png(self, svg_data: bytes,
                width: int | None = None,
                height: int | None = None) -> bytes:
        """Convert SVG bytes to PNG bytes."""
        logger.debug("Converting SVG to PNG - Size: %s bytes, Dimensions: %sx%s", len(svg_data), width, height)
        result = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height
        )
        logger.debug("SVG to PNG conversion complete - Output size: %s bytes", len(result))
        return result

    def _detect_image_mime(self, data: bytes) -> str | None:
        """זיהוי סוג MIME של תמונה מבוסס על חתימה בינארית."""
        logger.debug("Detecting image MIME type - Data size: %s bytes", len(data))
        head = data[:512]
        low = head.lstrip().lower()
        if b"\x00" not in head and (
            low.startswith(b"<svg")
            or (low.startswith(b"<?xml") and b"<svg" in low)
            or b'xmlns="http://www.w3.org/2000/svg"' in low
        ):
            logger.debug("Detected MIME type: image/svg+xml")
            return "image/svg+xml"

        elif data.startswith(b"\xff\xd8\xff"):
            logger.debug("Detected MIME type: image/jpeg")
            return "image/jpeg"

        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            logger.debug("Detected MIME type: image/png")
            return "image/png"

        elif data.startswith(b"GIF8"):
            logger.debug("Detected MIME type: image/gif")
            return "image/gif"

        elif data.startswith(b"BM"):
            logger.debug("Detected MIME type: image/bmp")
            return "image/bmp"

        elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            logger.debug("Detected MIME type: image/webp")
            return "image/webp"

        elif data.startswith(b"\x00\x00\x01\x00"):
            logger.debug("Detected MIME type: image/x-icon")
            return "image/x-icon"

        elif data.startswith((b"II*\x00", b"MM\x00*")):
            logger.debug("Detected MIME type: image/tiff")
            return "image/tiff"

        elif data:
            try:
                detected = magic.from_buffer(data, mime=True)
                logger.debug("Detected MIME type via magic library: %s", detected)
                return detected
            except Exception as e:
                logger.warning("Magic library detection failed: %s, using fallback", e)
                return "application/octet-stream"

        logger.warning("Could not detect MIME type, using fallback")
        return "application/octet-stream"

    def _image_to_base64_data_uri(self, image: bytes, mime_type: str) -> str:
        logger.debug(
            "Converting image to base64 data URI - MIME: %s, Size: %s bytes",
            mime_type,
            len(image),
        )
        if mime_type == "image/svg+xml":
            logger.debug("Converting SVG to PNG before base64 encoding")
            image = self._svg_to_png(image)
            mime_type = "image/png"

        b64 = base64.b64encode(image).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64}"
        logger.debug("Base64 encoding complete - Data URI length: %s", len(data_uri))
        return data_uri

    def _is_base64_string(self, s: str) -> bool:
        try:
            if s.startswith("data:image"):
                s = s.split(",", 1)[1]
            base64.b64decode(s, validate=True)
            return True
        except (binascii.Error, ValueError):
            return False

    def _validate_response_structure(self, response_json: dict) -> None:
        """Validate that the LLM response matches the expected structure."""
        logger.debug("Validating LLM response structure")
        logger.debug("Response JSON: %s", response_json)

        if not isinstance(response_json, dict):
            logger.error("Response is not a dict: %s", type(response_json))
            raise ResponseValidationError(
                message="Top-level response must be a JSON object",
                parsed_response=str(response_json))

        response_condition = response_json.keys()
        missing_conditions = set(self.CONDITIONS_CHECK) - response_condition
        if missing_conditions:
            logger.error("Missing required conditions: %s", missing_conditions)
            raise ResponseValidationError(
                message=f"missing conditions: {missing_conditions}",
                parsed_response=str(response_json),
            )

        extra_conditions = response_condition - set(self.CONDITIONS_CHECK)
        if extra_conditions:
            logger.warning("Unexpected conditions found: %s", extra_conditions)
            raise ResponseValidationError(
                message=f"has unexpected conditions: {extra_conditions}",
                parsed_response=str(response_json),
            )

        for condition, value in response_json.items():
            if value not in ("Yes", "No"):
                logger.error("Invalid value for condition '%s': %s (expected 'Yes' or 'No')", condition, value)
                raise ResponseValidationError(
                    message=f"Invalid value for condition '{condition}': {value}",
                    parsed_response=str(response_json),
                )
        logger.debug("Response structure validation passed")

    def analyze_image(self, image_content: str | bytes, mime: str | None) -> dict:
        logger.info("Starting image analysis")
        logger.debug("Input type: %s, MIME: %s", type(image_content), mime)

        if isinstance(image_content, str):
            logger.debug("Image content is string, processing...")
            if not self._is_base64_string(image_content):
                logger.debug("String is file path, reading file: %s", image_content)
                with open(image_content, "rb") as img_file:
                    image_content = img_file.read()
                logger.debug("File read, size: %s bytes", len(image_content))
            else:
                logger.debug("String is base64, decoding to bytes")
                s = image_content
                if s.startswith("data:image"):
                    s = s.split(",", 1)[1]
                image_content = base64.b64decode(s, validate=True)
                logger.debug("Base64 decoded, size: %s bytes", len(image_content))

        logger.debug("Image content size: %s bytes", len(image_content))

        if mime is None:
            logger.debug("MIME type not provided, detecting...")
            mime = self._detect_image_mime(image_content)
            logger.info("Detected MIME type: %s", mime)

        if mime == 'image/svg+xml':
            logger.debug("Converting SVG to PNG for LLM processing")
            image_content = self._svg_to_png(image_content)
            mime = 'image/png'

        logger.debug("Converting image to base64 data URI")
        image_content = self._image_to_base64_data_uri(image_content, mime_type=mime)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_content},
                    }
                ],
            },
        ]
        logger.info("Sending image to LLM for analysis")
        logger.debug("Data URI preview: %s...", image_content[:50])
        logger.debug("System prompt length: %s characters", len(self.SYSTEM_PROMPT))

        llm_response = self.llm.create_chat_completion(messages=messages, temperature=0.0)
        logger.debug("LLM response received")
        self.llm.reset()
        logger.debug("LLM context reset")

        response_content = llm_response["choices"][0]["message"]["content"]
        logger.debug("LLM response content length: %s characters", len(response_content))
        logger.debug("LLM response preview: %s...", response_content[:200])

        try:
            response_json = json.loads(response_content)
            logger.debug("Successfully parsed LLM response as JSON")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Raw response: %s", response_content)
            raise ResponseValidationError(
                message="Failed to parse LLM response as JSON",
                raw_response=response_content,
            ) from e

        self._validate_response_structure(response_json)
        logger.info("Image analysis complete - Result: %s", response_json)
        return response_json
