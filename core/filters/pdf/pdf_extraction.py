"""
Extract text and images from PDF bytes using PyMuPDF.
"""
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_pdf_text_and_images(pdf_bytes: bytes) -> Tuple[str, List[Tuple[int, int, bytes, str]]]:
    """
    Extract full text and all images from a PDF.

    Returns:
        (full_text, [(page_index, xref, image_bytes, mime_type), ...])
        If PyMuPDF not available or on error, returns ("", []).
    """
    if not pdf_bytes or len(pdf_bytes) < 100:
        return "", []
    if fitz is None:
        logger.warning("PyMuPDF not installed; PDF extraction skipped")
        return "", []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("Failed to open PDF: %s", e)
        return "", []

    text_parts: List[str] = []
    images: List[Tuple[int, int, bytes, str]] = []
    seen_xrefs: set = set()

    try:
        for page_idx, page in enumerate(doc):
            try:
                text_parts.append(page.get_text("text") or "")
            except Exception as e:
                logger.debug("Page get_text failed: %s", e)
            for xref in page.get_images():
                if not isinstance(xref, (list, tuple)) or len(xref) < 1:
                    continue
                xref_num = xref[0] if isinstance(xref[0], int) else int(xref[0])
                if xref_num in seen_xrefs:
                    continue
                seen_xrefs.add(xref_num)
                try:
                    img = doc.extract_image(xref_num)
                    if img and isinstance(img, dict):
                        raw = img.get("image")
                        ext = (img.get("ext") or "png").lower()
                        if raw:
                            mime = "image/png" if ext == "png" else "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                            images.append((page_idx, xref_num, bytes(raw), mime))
                except Exception as e:
                    logger.debug("Extract image xref %s failed: %s", xref_num, e)
        doc.close()
    except Exception as e:
        logger.warning("PDF extraction error: %s", e)
        try:
            doc.close()
        except Exception:
            pass
        return "\n".join(text_parts), images

    return "\n".join(text_parts), images
