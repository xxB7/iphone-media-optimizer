import logging
import os
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.logging import RichHandler

console = Console(force_terminal=True)

_logger = None

def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"optimizer_{timestamp}.log")

    logger = logging.getLogger("iPhoneOptimizer")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    # Rich Console Handler
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)

    # File Handler (Captures everything down to DEBUG)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    _logger = logger
    return logger

def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger
