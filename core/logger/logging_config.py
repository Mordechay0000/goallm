"""
Central logging setup: file + stdout, uncaught-exception handler.
Uses project-root .storage so logs are consistent regardless of CWD.
"""
import logging
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = _project_root / ".storage"
LOG_FILE = STORAGE_DIR / "app.log"


def setup_logging() -> None:
    """Configure logging to file and stdout. Idempotent modulo basicConfig."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    log = logging.getLogger(__name__)
    log.info("Logging system initialized")
    log.debug("Log file: %s, level: DEBUG", LOG_FILE)

    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _excepthook
