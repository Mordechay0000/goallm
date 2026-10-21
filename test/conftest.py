"""
Test isolation: every test session gets its own storage directory (DBs, secrets, uploads),
set BEFORE any project module reads data.constants.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="goallm-test-")
os.environ.setdefault("GOALLM_STORAGE_DIR", _TMP)
os.environ.setdefault("IMAGE_ANALYZER", "simulated")
os.environ.setdefault("TRUSTED_PROXY_IPS", "127.0.0.1,::1")
os.environ.setdefault("PROXY_REQUIRE_AUTH", "1")
os.environ.setdefault("FILTER_BIND_BASE_URL", "https://filter.example.org")
os.environ.setdefault("CRM_BASE_URL", "https://filter.example.org")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
