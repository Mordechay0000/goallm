import base64
import hashlib
import logging

from core.image_processing.analyzers.base import ImageAnalyzer

logger = logging.getLogger(__name__)

CONDITIONS_CHECK = (
    "female_visible_9_plus",
    "female_3_to_9_partial_clothing",
    "female_under_3_minimal_clothing",
    "boys_teens_men_exposed_or_bathing",
    "any_visible_body_exposure",
)


class SimulatedImageAnalyzer(ImageAnalyzer):
    CONDITIONS_CHECK = CONDITIONS_CHECK

    def __init__(self) -> None:
        logger.info("Initializing SimulatedImageAnalyzer")

    def analyze_image(self, image_content: str | bytes, mime: str | None) -> dict:
        logger.info("Starting simulated image analysis")
        
        # Convert to bytes
        if isinstance(image_content, str):
            # Check if it's a base64 data URI
            if image_content.startswith("data:image"):
                image_content = base64.b64decode(image_content.split(",", 1)[1])
            else:
                # Assume it's a file path
                with open(image_content, "rb") as f:
                    image_content = f.read()
        
        # Calculate hash
        image_hash = hashlib.md5(image_content).digest()
        hash_int = int.from_bytes(image_hash[:4], byteorder='big')
        
        # Determine result based on hash % 2
        is_even = (hash_int % 2) == 0
        
        # Build response: first condition "Yes" if even, all others "No"
        result = {}
        for i, condition in enumerate(self.CONDITIONS_CHECK):
            if i == 0 and is_even:
                result[condition] = "Yes"
            else:
                result[condition] = "No"
        
        logger.info(f"Simulated image analysis complete - Result: {result}")
        return result
