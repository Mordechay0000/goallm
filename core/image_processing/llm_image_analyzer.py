import binascii
import json
import logging
import cairosvg
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler
import base64

import magic

logger = logging.getLogger(__name__)


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




class LLMImageAnalyzer(): 
    MODEL_PATH = "models/Qwen3VL-8B-Instruct-Q4_k_m.gguf"
    NMPROJ_MODEL_PATH = "models/qwen3_vl_8B_Q8/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
    
    CONDITIONS_CHECK = (
        "female_visible_9_plus",
        "female_3_to_9_partial_clothing",
        "female_under_3_minimal_clothing",
        "boys_teens_men_exposed_or_bathing",
        "any_visible_body_exposure"
    )
    
    def __init__(self): 
        logger.info("Initializing LLMImageAnalyzer")
        # Load system prompt
        try:
            logger.debug("Loading system prompt from config/llm/system_prompt.txt")
            with open("config/llm/system_prompt.txt", "r", encoding="utf-8") as f:
                self.SYSTEM_PROMPT = f.read()
            logger.debug(f"System prompt loaded, length: {len(self.SYSTEM_PROMPT)} characters")
        except FileNotFoundError:
            logger.error("System prompt file not found")
            raise FileNotFoundError(
                f"System prompt file not found: config/llm/system_prompt.txt"
            )
        
        # Check if model files exist
        import os
        logger.debug(f"Checking model files - Main: {self.MODEL_PATH}, MMProj: {self.NMPROJ_MODEL_PATH}")
        if not os.path.exists(self.MODEL_PATH):
            logger.error(f"Model file not found: {self.MODEL_PATH}")
            raise FileNotFoundError(
                f"Model file not found: {self.MODEL_PATH}. "
                f"Please ensure the model file exists in the models/ directory."
            )
        if not os.path.exists(self.NMPROJ_MODEL_PATH):
            logger.error(f"MMProj model file not found: {self.NMPROJ_MODEL_PATH}")
            raise FileNotFoundError(
                f"MMProj model file not found: {self.NMPROJ_MODEL_PATH}. "
                f"Please ensure the mmproj model file exists in the models/ directory."
            )
        logger.info("Model files found, loading LLM model...")
        
        self.llm = Llama(
            model_path=self.MODEL_PATH,
            chat_handler=Qwen3VLChatHandler(clip_model_path=self.NMPROJ_MODEL_PATH),
            n_gpu_layers=-1,  # Offload all layers to the GPU
            n_ctx=10240,  # Set the context window size
            swa_full=False,
        )
        logger.info("LLMImageAnalyzer initialized successfully")

    def _svg_to_png(self, svg_data: bytes,
                width: int | None = None,
                height: int | None = None) -> bytes:
        """
        Convert SVG bytes to PNG bytes.
        width/height optional; if None uses SVG viewBox.
        """
        logger.debug(f"Converting SVG to PNG - Size: {len(svg_data)} bytes, Dimensions: {width}x{height}")
        result = cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height
        )
        logger.debug(f"SVG to PNG conversion complete - Output size: {len(result)} bytes")
        return result
    

    def _detect_image_mime(self, data: bytes) -> str | None:
        """זיהוי סוג MIME של תמונה מבוסס על חתימה בינארית."""
        logger.debug(f"Detecting image MIME type - Data size: {len(data)} bytes")
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

        # fallback – only if everything above failed
        elif data:
            try:
                detected = magic.from_buffer(data, mime=True)
                logger.debug(f"Detected MIME type via magic library: {detected}")
                return detected
            except Exception as e:
                logger.warning(f"Magic library detection failed: {e}, using fallback")
                return "application/octet-stream"

        logger.warning("Could not detect MIME type, using fallback")
        return "application/octet-stream"



    def _image_to_base64_data_uri(self, image:  bytes, mime_type: str) -> str:
            logger.debug(f"Converting image to base64 data URI - MIME: {mime_type}, Size: {len(image)} bytes")
            if mime_type == 'image/svg+xml':
                # SVG images should be directly encoded as UTF-8 text
                logger.debug("Converting SVG to PNG before base64 encoding")
                image = self._svg_to_png(image)
                mime_type = 'image/png'

            base64_data = base64.b64encode(image).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{base64_data}"
            logger.debug(f"Base64 encoding complete - Data URI length: {len(data_uri)} characters")
            return data_uri

    def _is_base64_string(self, s: str) -> bool:
        try:
            # remove common headers if exist
            if s.startswith("data:image"):
                s = s.split(",", 1)[1]

            base64.b64decode(s, validate=True)
            return True
        except (binascii.Error, ValueError):
            return False


    def _validate_response_structure(self,
        response_json: dict,
    ) -> None:
        """
        Validate that the LLM response matches the expected structure.

        Returns:
            None if valid
            dict with "error" if invalid
        """
        logger.debug("Validating LLM response structure")
        logger.debug(f"Response JSON: {response_json}")

        if not isinstance(response_json, dict):
            logger.error(f"Response is not a dict: {type(response_json)}")
            raise ResponseValidationError(
                message = "Top-level response must be a JSON object",
                parsed_response=str(response_json))
        
        response_condition = response_json.keys()
        # Check that all expected conditions exist
        missing_conditions = set(self.CONDITIONS_CHECK) - response_condition
        if missing_conditions:
            logger.error(f"Missing required conditions: {missing_conditions}")
            raise ResponseValidationError(
                message = f"missing conditions: {missing_conditions}",
                parsed_response=str(response_json),
            )

        # Check for unexpected conditions (optional but recommended)
        extra_conditions = response_condition - set(self.CONDITIONS_CHECK)
        if extra_conditions:
            logger.warning(f"Unexpected conditions found: {extra_conditions}")
            raise ResponseValidationError(
                message = f"has unexpected conditions: {extra_conditions}",
                parsed_response=str(response_json),
            )

        # Validate values
        for condition, value in response_json.items():
            if value not in ("Yes", "No"):
                logger.error(f"Invalid value for condition '{condition}': {value} (expected 'Yes' or 'No')")
                raise ResponseValidationError(
                    message = f"Invalid value for condition '{condition}': {value}",
                    parsed_response=str(response_json),
                )
        
        logger.debug("Response structure validation passed")
            

    def analyze_image(self, image_content: str|bytes, mime) -> dict:
        logger.info("Starting image analysis")
        logger.debug(f"Input type: {type(image_content)}, MIME: {mime}")
        
        if isinstance(image_content, str):
            logger.debug("Image content is string, processing...")
            if not self._is_base64_string(image_content):
                logger.debug(f"String is file path, reading file: {image_content}")
                with open(image_content, "rb") as img_file:
                    image_content: bytes = img_file.read()
                logger.debug(f"File read, size: {len(image_content)} bytes")
            else:
                logger.debug("String is base64, handling...")
                #Todo: handle base64 string
                pass
        
        logger.debug(f"Image content size: {len(image_content)} bytes")
        
        # Detect MIME type if not provided
        if mime is None:
            logger.debug("MIME type not provided, detecting...")
            mime = self._detect_image_mime(image_content)
            logger.info(f"Detected MIME type: {mime}")
        
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
        logger.debug(f"Data URI preview: {image_content[:50]}...")
        logger.debug(f"System prompt length: {len(self.SYSTEM_PROMPT)} characters")
        
        llm_response = self.llm.create_chat_completion(messages=messages, temperature=0.0)
        logger.debug("LLM response received")
        self.llm.reset()
        logger.debug("LLM context reset")
        
        response_content = llm_response["choices"][0]["message"]["content"]
        logger.debug(f"LLM response content length: {len(response_content)} characters")
        logger.debug(f"LLM response preview: {response_content[:200]}...")
        
        try:
            response_json = json.loads(response_content)
            logger.debug("Successfully parsed LLM response as JSON")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_content}")
            raise ResponseValidationError(
                message = "Failed to parse LLM response as JSON",
                raw_response=response_content,
            ) from e
        
        self._validate_response_structure(response_json)
        logger.info(f"Image analysis complete - Result: {response_json}")
        return response_json
