"""
Search result filters (e.g. Google: hide blocked/unknown result links).
"""
from core.filters.search.google_search_filter import filter_google_search_html, is_google_search_page

__all__ = ["filter_google_search_html", "is_google_search_page"]
