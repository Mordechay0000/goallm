"""
Central logging setup: file + stdout, uncaught-exception handler.
"""
import logging
import os
import sys

STORAGE_DIR = ".storage"
LOG_FILE = ".storage/app.log"


def setup_logging() -> None:
    """Configure logging to file and stdout. Idempotent modulo basicConfig."""
    os.makedirs(STORAGE_DIR, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
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
