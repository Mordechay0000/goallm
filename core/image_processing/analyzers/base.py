"""
Abstract base for image analyzers.
"""
from abc import ABC, abstractmethod


class ImageAnalyzer(ABC):
    """Analyzes images and returns a structured result (e.g. policy conditions)."""

    @abstractmethod
    def analyze_image(self, image_content: str | bytes, mime: str | None) -> dict:
        """
        Analyze image and return a dict of condition -> "Yes"|"No".

        Args:
            image_content: Raw image bytes or path/base64 string.
            mime: MIME type or None to detect.

        Returns:
            Dict with keys like female_visible_9_plus, etc., values "Yes" or "No".
        """
        pass
