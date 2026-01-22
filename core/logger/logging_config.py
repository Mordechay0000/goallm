# logging_config.py
import logging
import sys
import traceback
import os

LOG_FILE = ".storage/app.log"

def setup_logging():
    # Ensure .storage directory exists
    os.makedirs(".storage", exist_ok=True)
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    
    # Log that logging is set up
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    logger.debug(f"Log file: {LOG_FILE}")
    logger.debug(f"Log level: DEBUG")

    # Catch *all* uncaught exceptions
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception
