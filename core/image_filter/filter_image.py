import binascii
import json
import mimetypes
import cairosvg
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler
import base64


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




class FilterImage(): 
    MODEL_PATH = "models/Qwen3VL-8B-Instruct-Q4_k_m.gguf"
    NMPROJ_MODEL_PATH = "models/qwen3_vl_8B_Q8/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
    SYSTEM_PROMPT = open("config/llm/system_prompt.txt", "r", encoding="utf-8").read()
    CONDITIONS_CHECK = (
        "female_visible_9_plus",
        "female_3_to_9_partial_clothing",
        "female_under_3_minimal_clothing",
        "boys_teens_men_exposed_or_bathing",
        "any_visible_body_exposure"
    )
    
    def __init__(self): 
        self.llm = Llama(
            model_path=self.MODEL_PATH,
            chat_handler=Qwen3VLChatHandler(clip_model_path=self.NMPROJ_MODEL_PATH),
            n_gpu_layers=-1,  # Offload all layers to the GPU
            n_ctx=10240,  # Set the context window size
            swa_full=False,
        )

    import cairosvg

    def _svg_to_png(self, svg_data: bytes,
                width: int | None = None,
                height: int | None = None) -> bytes:
        """
        Convert SVG bytes to PNG bytes.
        width/height optional; if None uses SVG viewBox.
        """
        return cairosvg.svg2png(
            bytestring=svg_data,
            output_width=width,
            output_height=height
        )


    def _image_to_base64_data_uri(self, image:  bytes, mime_type: str) -> str:
            if mime_type == 'image/svg+xml':
                # SVG images should be directly encoded as UTF-8 text
                image = self._svg_to_png(image, width=512, height=512)
                mime_type = 'image/png'

            base64_data = base64.b64encode(image).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"

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

        if not isinstance(response_json, dict):
            raise ResponseValidationError(
                message = "Top-level response must be a JSON object",
                parsed_response=str(response_json))
        
        response_condition = response_json.keys()
        # Check that all expected conditions exist
        missing_conditions = set(self.CONDITIONS_CHECK) - response_condition
        if missing_conditions:
            raise ResponseValidationError(
                message = f"missing conditions: {missing_conditions}",
                parsed_response=str(response_json),
            )

        # Check for unexpected conditions (optional but recommended)
        extra_conditions = response_condition - set(self.CONDITIONS_CHECK)
        if extra_conditions:
            raise ResponseValidationError(
                message = f"has unexpected conditions: {extra_conditions}",
                parsed_response=str(response_json),
            )

        # Validate values
        for condition, value in response_json.items():
            if value not in ("Yes", "No"):
                raise ResponseValidationError(
                    message = f"Invalid value for condition '{condition}': {value}",
                    parsed_response=str(response_json),
                )
            

    def analyze_image(self, image_content: str|bytes, mime) -> dict:
        if isinstance(image_content, str):
            if not self._is_base64_string(image_content):
                with open(image_content, "rb") as img_file:
                    image_content = self._image_to_base64_data_uri(img_file.read(), mime_type=mime)
        elif isinstance(image_content, bytes):
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
        print(f"Sending image to LLM: {image_content[0:20]}")
        llm_response = self.llm.create_chat_completion(messages=messages, temperature=0.0)
        self.llm.reset()
        response_content = llm_response["choices"][0]["message"]["content"]
        try:
            response_json = json.loads(response_content)
        except json.JSONDecodeError as e:
            raise ResponseValidationError(
                message = "Failed to parse LLM response as JSON",
                raw_response=response_content,
            ) from e
        self._validate_response_structure(response_json)
        print("\n\n\n\n\n\n\n" + response_content)
        return response_json
