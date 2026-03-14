"""
Filter Google search results HTML: add status icons next to results (blocked / not yet reviewed).
Does not break links; only adds a symbol beside each result.
Result text is censored with xxx by the normal text-filter rules; links are never disabled.
"""
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin, parse_qs

from bs4 import BeautifulSoup

from core.policy.policy_loader import get_policy_resolver
from core.filters.text.text_filter import filter_text_content

logger = logging.getLogger(__name__)

# Inline style for the status icon (small, RTL-friendly, no layout break)
ICON_STYLE = "display:inline;margin-left:0.25em;font-size:0.9em;text-decoration:none;"

# Google search hostnames (without www)
GOOGLE_SEARCH_HOSTS = ("google.com", "google.co.il", "google.co.uk", "google.de", "google.fr", "google.es", "google.it")

# URL prefixes that are internal/navigation, not result links
SKIP_PREFIXES = (
    "/search?",
    "https://www.google.com/search",
    "https://www.google.co.il/search",
    "https://google.com/search",
    "https://google.co.il/search",
    "https://accounts.google.com",
    "https://support.google.com",
    "https://policies.google.com",
    "https://maps.google.com",
    "/url?q=",  # Google redirect wrapper - we'll unwrap below
)


def is_google_search_page(url: str) -> bool:
    """True if URL is a Google search page."""
    if not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        if host not in GOOGLE_SEARCH_HOSTS:
            return False
        path = (parsed.path or "").lower()
        return "/search" in path or path == "/" and "q=" in (parsed.query or "")
    except Exception:
        return False


def _unwrap_google_redirect(href: str) -> str:
    """If href is /url?q=... return the q= value (actual result URL)."""
    if not href or "url?q=" not in href:
        return href
    try:
        parsed = urlparse(href if "://" in href else f"https://www.google.com{href}")
        qs = parse_qs(parsed.query)
        urls = qs.get("q", [])
        if urls:
            return urls[0]
    except Exception:
        pass
    return href


def _is_internal_or_skip(href: str, base_url: str) -> bool:
    """True if link should be skipped (internal, nav, etc.)."""
    if not href or href.startswith("#") or href.startswith("javascript:"):
        return True
    full = href if "://" in href else urljoin(base_url or "https://www.google.com/", href)
    full_lower = full.lower()
    for skip in SKIP_PREFIXES:
        if skip in full_lower:
            return True
    try:
        parsed = urlparse(full)
        host = (parsed.hostname or "").lower()
        if "google." in host or "google.com" in host or "gstatic.com" in host or "youtube.com" in host and "google" in full_lower:
            return True
    except Exception:
        pass
    return False


def _add_icon_to_link(soup: BeautifulSoup, tag, state: str) -> None:
    """Prepend a status icon (blocked or review) at the start of the link. Does not remove existing content."""
    style = ICON_STYLE
    if state == "block":
        icon = soup.new_tag("span", attrs={
            "class": "goallm-result-blocked",
            "style": style,
            "title": "אתר חסום",
            "aria-label": "אתר חסום",
        })
        icon.string = "🔒"
    else:
        icon = soup.new_tag("span", attrs={
            "class": "goallm-result-review",
            "style": style,
            "title": "עדיין לא נבדק",
            "aria-label": "עדיין לא נבדק",
        })
        icon.string = "?"
    tag.insert(0, icon)


def _is_our_icon_span(child) -> bool:
    """True if this element is the status icon we added (do not remove when censoring)."""
    if not hasattr(child, "name") or child.name != "span":
        return False
    cls = child.get("class") or []
    return "goallm-result-blocked" in cls or "goallm-result-review" in cls


def _apply_text_filter_to_result_link(tag, user_id: Optional[int], link_text: str) -> bool:
    """
    Run text filter on the link's visible text (pass link_text before icon was added).
    Replace text with the filtered output (xxx masking by normal text-filter rules).
    Links are never broken – if the site is problematic it will be blocked on visit.
    Keeps our status icon (🔒/?) if present. Returns True if content was changed.
    """
    text = (link_text or "").strip()
    if not text or len(text) < 2:
        return False
    try:
        filtered_bytes, _block_page, _block_reason, _debug = filter_text_content(
            text.encode("utf-8"),
            url="",
            content_type="text/plain; charset=utf-8",
            text_filter_enabled=True,
            rule_context=None,
        )
        if not filtered_bytes:
            return False
        filtered_str = filtered_bytes.decode("utf-8", errors="replace").strip()
        if filtered_str == text.strip():
            return False
        # Replace link text with filtered (xxx) version; leave icon spans; do not touch href
        for child in list(tag.children):
            if _is_our_icon_span(child):
                continue
            if hasattr(child, "string") and child.string:
                child.replace_with(filtered_str)
                return True
            if hasattr(child, "name") and child.name and not _is_our_icon_span(child):
                child.string = filtered_str
                return True
    except Exception as e:
        logger.debug("Text filter on result text failed: %s", e)
    return False


def filter_google_search_html(
    html_bytes: bytes,
    page_url: str,
    encoding: str,
    user_id: Optional[int],
) -> bytes:
    """
    Add status icons next to search results: 🔒 for blocked URL, ? for review (not yet checked).
    Does not break links or replace titles; only prepends an icon.
    Text filter: result text is censored with xxx by normal text-filter rules; links stay intact.
    """
    if not html_bytes or not is_google_search_page(page_url):
        return html_bytes
    try:
        soup = BeautifulSoup(html_bytes, "html.parser")
    except Exception as e:
        logger.warning("Google search filter: parse failed %s", e)
        return html_bytes

    try:
        resolver = get_policy_resolver(user_id)
    except Exception as e:
        logger.warning("Google search filter: policy resolver failed %s", e)
        return html_bytes

    modified = False
    for tag in soup.find_all("a", href=True):
        href = (tag.get("href") or "").strip()
        if _is_internal_or_skip(href, page_url):
            continue
        actual_url = _unwrap_google_redirect(href)
        if not actual_url or actual_url.startswith("#"):
            continue
        if "://" not in actual_url:
            actual_url = urljoin(page_url or "https://www.google.com/", actual_url)
        try:
            rule = resolver.resolve(actual_url, "html")
            state = (rule or {}).get("state")
            link_text = tag.get_text(separator=" ", strip=True)
            if state in ("block", "review"):
                _add_icon_to_link(soup, tag, state)
                modified = True
            # If text filter blocks the result's visible text, censor it (and break link)
            if _apply_text_filter_to_result_link(tag, user_id, link_text):
                modified = True
        except Exception as e:
            logger.debug("Resolve failed for %s: %s", actual_url[:60], e)

    if not modified:
        return html_bytes
    try:
        out = soup.encode(encoding, formatter="html")
        return out
    except Exception as e:
        logger.warning("Google search filter: encode failed %s", e)
        return html_bytes
