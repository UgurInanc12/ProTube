"""Application-wide logging to sessions directory."""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime


def setup_logging(base_dir: Path) -> logging.Logger:
    """Configure file logging with timestamped log file.

    Log file: <base_dir>/protube_YYYY-MM-DD_HHMMSS.log
    """
    base_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_path = base_dir / f"protube_{timestamp}.log"

    logger = logging.getLogger("protube")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Also log unhandled exceptions
    def exception_handler(exc_type, exc_value, exc_tb):
        logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

    sys.excepthook = exception_handler

    # sys.excepthook never sees failures in background threads; log those too.
    import threading

    def thread_exception_handler(args):
        logger.critical(
            "Unhandled exception in thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_exception_handler

    logger.info(f"ProTube started | log: {log_path}")
    logger.info(f"Python: {sys.version} | frozen: {getattr(sys, 'frozen', False)}")
    if getattr(sys, "frozen", False):
        logger.info(f"EXE path: {sys.executable}")
    logger.info(f"Sessions dir: {base_dir}")

    return logger
