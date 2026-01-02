import json
import mimetypes
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler
import base64


class ResponseValidationError(Exception):
    def __init__(
        self,
        *,
        details: dict | None = None,
        raw_response: str | None = None,
        parsed_response: dict | None = None,
        item_key: str | None = None,
    ):
        super().__init__()
        self.details = details
        self.raw_response = raw_response
        self.parsed_response = parsed_response
        self.item_key = item_key

    def __str__(self):
        parts = [str(self)]
        if self.item_key:
            parts.append(f"item={self.item_key}")
        if self.details:
            parts.append(f"details={self.details}")
        return " | ".join(parts)

    def to_dict(self):
        return {
            "error": self.message,
            "item_key": self.item_key,
            "details": self.details,
            "raw_response": self.raw_response,
            "parsed_response": self.parsed_response,
        }




class FilterImage(): 
    MODEL_PATH = "models/qwen_3_vl_8B_Q8/Qwen3VL-8B-Instruct-Q8_0.gguf"
    NMPROJ_MODEL_PATH = "models/qwen_3_vl_8B_Q8/mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"
    SYSTEM_PROMPT = open("../system_prompt.txt", "r", encoding="utf-8").read()
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


    def _image_to_base64_data_uri(self, file_path):
        with open(file_path, "rb") as img_file:
            base64_data = base64.b64encode(img_file.read()).decode("utf-8")
            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            return f"data:{mime_type};base64,{base64_data}"



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
                "Top-level response must be a JSON object",
                parsed_response=str(response_json))
        for item_key, item_data in response_json.items():
            if not isinstance(item_key, str):
                raise ResponseValidationError(
                    f"Invalid item key type: {item_key}",
                    parsed_response=str(response_json),
                    item_key=item_key,
                )

            if not isinstance(item_data, dict):
                raise ResponseValidationError(
                    f"Item '{item_key}' must be an object",
                    parsed_response=str(response_json),
                    item_key=item_key,
                )

            # Check that all expected conditions exist
            missing_conditions = set(self.CONDITIONS_CHECK) - item_data.keys()
            if missing_conditions:
                raise ResponseValidationError(
                    f"Item '{item_key}' is missing conditions: {missing_conditions}",
                    parsed_response=str(response_json),
                    item_key=item_key,
                )

            # Check for unexpected conditions (optional but recommended)
            extra_conditions = item_data.keys() - set(self.CONDITIONS_CHECK)
            if extra_conditions:
                raise ResponseValidationError(
                    f"Item '{item_key}' has unexpected conditions: {extra_conditions}",
                    parsed_response=str(response_json),
                    item_key=item_key,
                )

            # Validate values
            for condition, value in item_data.items():
                if value not in ("Yes", "No"):
                    raise ResponseValidationError(
                        f"Invalid value for condition '{condition}' in '{item_key}': {value}",
                        parsed_response=str(response_json),
                        item_key=item_key,
                    )


    def _evaluate_item_conditions(self, 
        item_data: dict[str, str],
    ) -> tuple[bool, ...]:
        """
        Evaluate whether each condition is satisfied for a single item.
        """
        return tuple(item_data.get(condition) == "Yes" for condition in self.CONDITIONS_CHECK)


    def _evaluate_all_items(self,
        all_items: dict[str, dict[str, str]],
    ) -> tuple[tuple[bool, ...], ...]:
        """
        Evaluate conditions for all items.
        """
        return tuple(
            self._evaluate_item_conditions(item_data)
            for item_data in all_items.values()
        )



    def analyze_image(self, file_path):
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": self._image_to_base64_data_uri(file_path)},
                    }
                ],
            },
        ]
        llm_response = self.llm.create_chat_completion(messages=messages, temperature=0.0)
        response_content = llm_response["choices"][0]["message"]["content"]
        try:
            response_json = json.loads(response_content)
        except json.JSONDecodeError as e:
            raise ResponseValidationError(
                "Failed to parse LLM response as JSON",
                raw_response=response_content,
            ) from e
        self._validate_response_structure(response_json)
        
        conditions_status = self._evaluate_all_items(response_json)
        return conditions_status
