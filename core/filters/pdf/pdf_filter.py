"""
Filter PDF: run text filter and image status on extracted content; reassemble PDF with optional distortion warning.

- Text: per-block (paragraph) masking with X's when a block contains a hard word; block the entire document
  when the ratio of blocks with detection passes the threshold, or when the hidden score of the whole text does
  (the same scoring as web pages: suspicious words, windows, diversity, Torah / medical context).
- Images: replace each image with status (blocked/checking/allowed) like on web pages.
"""
import io
import logging
from typing import Optional, Tuple, List, Any

from core.filters.pdf.pdf_extraction import extract_pdf_text_and_images
from core.filters.text.text_filter import _filter_plain_text, filter_paragraph_for_pdf, filter_text_content
from core.filters.text.text_filter_config import (
    MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK,
    MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK,
)
from core.filters.image.image_status_manager import get_image_with_status

logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# Placeholder text for distortion warning (Hebrew)
PDF_DISTORTION_WARNING_TEXT = "יתכן שהקובץ ייצא משובש – הסינון שינה תמונות או טקסט."


def _blocked_pdf_html(pdf_url: str, rule_context: Optional[dict], block_reason: str) -> bytes:
    from core.flow.site_policy_pages import get_blocked_page_bytes
    return get_blocked_page_bytes(
        request_url=pdf_url,
        rule=rule_context or {},
        tags=(rule_context.get("tags") or []) if rule_context else [],
        block_reason="text_filter",
        block_reason_detail=block_reason or "",
    )


def _block_text_from_dict(block: dict) -> Tuple[str, Optional[Any]]:
    """Extract full text and bbox from a get_text('dict') block. Returns (text, rect or None)."""
    lines = block.get("lines") or []
    parts = []
    for line in lines:
        for span in line.get("spans") or []:
            parts.append(span.get("text") or "")
    text = "".join(parts)
    bbox = block.get("bbox")
    if fitz and bbox and len(bbox) >= 4:
        return text, fitz.Rect(bbox)
    return text, None


def _apply_pdf_text_filter(
    doc: "fitz.Document",
    pdf_url: str,
    rule_context: Optional[dict],
) -> Tuple[bool, str]:
    """
    Run paragraph-style text filter on every text block in the PDF.
    - Mask each block that contains a bad word (replace with X's via redaction).
    - If (blocks_with_detection / total_blocks) >= threshold and count >= min, return (True, reason) to block page.
    Returns (block_page, block_reason).
    """
    total_blocks = 0
    blocks_with_detection = 0
    pages_with_redactions: List[int] = []
    all_text: List[str] = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        d = page.get_text("dict", sort=True)
        blocks = d.get("blocks") or []
        for block in blocks:
            block_text, rect = _block_text_from_dict(block)
            if not block_text.strip() or rect is None:
                continue
            total_blocks += 1
            all_text.append(block_text)
            masked, has_detection = filter_paragraph_for_pdf(block_text)
            if has_detection:
                blocks_with_detection += 1
                try:
                    # Replace block content with masked text (X's and spaces; Base 14 supports ASCII)
                    page.add_redact_annot(rect, text=masked, fill=(1, 1, 1))
                    if page_idx not in pages_with_redactions:
                        pages_with_redactions.append(page_idx)
                except Exception as e:
                    logger.debug("PDF redact annot failed for block: %s", e)
                    try:
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        if page_idx not in pages_with_redactions:
                            pages_with_redactions.append(page_idx)
                    except Exception as e2:
                        logger.debug("PDF redact (fill only) failed: %s", e2)

    for page_idx in pages_with_redactions:
        try:
            doc[page_idx].apply_redactions()
        except Exception as e:
            logger.warning("PDF apply_redactions failed on page %s: %s", page_idx, e)

    block_page = False
    block_reason = ""
    if total_blocks > 0 and blocks_with_detection > 0:
        pct = blocks_with_detection / total_blocks
        if (
            blocks_with_detection >= MIN_COMPONENTS_WITH_DETECTION_FOR_PAGE_BLOCK
            and pct >= MIN_PERCENTAGE_COMPONENTS_FOR_PAGE_BLOCK
        ):
            block_page = True
            block_reason = "pdf_paragraphs_with_detection: %d/%d (%.0f%%)" % (
                blocks_with_detection, total_blocks, pct * 100,
            )
    if not block_page and all_text:
        _masked, score_block, score_reason, _debug = _filter_plain_text("\n".join(all_text))
        if score_block:
            block_page, block_reason = True, "pdf_" + score_reason
    return block_page, block_reason


def filter_pdf_response(
    pdf_bytes: bytes,
    pdf_url: str,
    referer_url: Optional[str],
    rule_context: Optional[dict],
    distortion_warning_enabled: bool,
    filter_text: bool = True,
    filter_images: bool = True,
) -> Tuple[Optional[bytes], Optional[bytes], bool]:
    """
    Filter a PDF: optionally text (per-block mask + block page if needed) and/or images (replace by status).

    When both filter_text and filter_images are False, returns original bytes unchanged.
    """
    if not pdf_bytes or len(pdf_bytes) < 100:
        return pdf_bytes, None, False
    if not filter_text and not filter_images:
        return pdf_bytes, None, False
    if fitz is None:
        logger.warning("PyMuPDF not installed; PDF filter skipped")
        return pdf_bytes, None, False

    try:
        full_text, image_list = extract_pdf_text_and_images(pdf_bytes)
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return pdf_bytes, None, False

    # 1) Quick block decision from full text (ratio-based)
    if filter_text and full_text and full_text.strip():
        try:
            _filtered_bytes, block_page, block_reason, _ = filter_text_content(
                full_text.encode("utf-8"),
                url=pdf_url,
                content_type="text/plain; charset=utf-8",
                text_filter_enabled=True,
                rule_context=rule_context,
            )
            if block_page:
                blocked_html = _blocked_pdf_html(pdf_url, rule_context, block_reason or "")
                logger.info("PDF blocked by text filter (full-text ratio) - URL: %s", pdf_url)
                return None, blocked_html, False
        except Exception as e:
            logger.warning("PDF text filter failed: %s", e)

    # 2) Open doc once for both text redaction and image replace
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        logger.warning("Failed to open PDF: %s", e)
        return pdf_bytes, None, False

    try:
        # 3) Text: per-block mask and paragraph-based block decision
        if filter_text:
            block_page, block_reason = _apply_pdf_text_filter(doc, pdf_url, rule_context)
            if block_page:
                doc.close()
                blocked_html = _blocked_pdf_html(pdf_url, rule_context, block_reason)
                logger.info("PDF blocked by paragraph-ratio - URL: %s reason: %s", pdf_url, block_reason)
                return None, blocked_html, False

        # 4) Image filtering: replace each image with status (blocked/checking/allowed)
        if filter_images and image_list:
            for page_idx, xref_num, img_bytes, mime in image_list:
                try:
                    replacement, _, _ = get_image_with_status(
                        image_data=img_bytes,
                        image_url=pdf_url,
                        referer_url=referer_url,
                        image_mime_type=mime,
                    )
                    if replacement:
                        doc[page_idx].replace_image(xref=xref_num, stream=replacement)
                except Exception as e:
                    logger.debug("Replace image xref %s failed: %s", xref_num, e)

        buf = io.BytesIO()
        doc.save(buf, deflate=True, garbage=4)
        out_bytes = buf.getvalue()
        doc.close()
    except Exception as e:
        logger.warning("PDF filter failed: %s", e, exc_info=True)
        try:
            doc.close()
        except Exception:
            pass
        return pdf_bytes, None, False

    distortion_added = False
    if distortion_warning_enabled:
        try:
            out_bytes, distortion_added = _add_distortion_warning_to_pdf(out_bytes)
        except Exception as e:
            logger.debug("Could not add PDF distortion warning: %s", e)

    return out_bytes, None, distortion_added


def _add_distortion_warning_to_pdf(pdf_bytes: bytes) -> Tuple[bytes, bool]:
    """Add overlay on first page with distortion warning text. Returns (new_pdf_bytes, True)."""
    if fitz is None:
        return pdf_bytes, False
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return pdf_bytes, False
        page = doc[0]
        rect = page.rect
        # Small text at top-right (RTL Hebrew)
        y0 = rect.y0 + 12
        x1 = rect.x1 - 12
        try:
            page.insert_text((x1, y0), PDF_DISTORTION_WARNING_TEXT, fontsize=9, fontname="helv")
        except Exception:
            page.insert_text((x1, y0), PDF_DISTORTION_WARNING_TEXT, fontsize=9)
        buf = io.BytesIO()
        doc.save(buf, deflate=True, garbage=4)
        out = buf.getvalue()
        doc.close()
        return out, True
    except Exception as e:
        logger.debug("_add_distortion_warning_to_pdf failed: %s", e)
        return pdf_bytes, False
