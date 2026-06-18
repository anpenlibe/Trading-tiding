"""Centralized logging setup for the trading bot.

``setup_logger()`` is the single logging entry point used across the codebase.
It returns a stdlib ``Logger`` with an optional rotating file handler, a
colorized console handler, and a shared rotating ``error.log`` that captures
ERROR+ (with file:line) from every module.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

# Logs live under data/logs/ at the repo root; created on import.
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class ColoredFormatter(logging.Formatter):
    """Console formatter that colors the whole line by log level."""

    COLORS = {
        logging.DEBUG: "\x1b[38;21m",
        logging.INFO: "\x1b[32m",
        logging.WARNING: "\x1b[33m",
        logging.ERROR: "\x1b[31m",
        logging.CRITICAL: "\x1b[31;1m",
    }
    RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        formatter = logging.Formatter(f"{color}{_LOG_FORMAT}{self.RESET}", datefmt=_DATE_FORMAT)
        return formatter.format(record)


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console_output: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """Configure and return a logger.

    Args:
        name: Logger name (usually ``__name__``).
        log_file: Optional per-module log filename (created under data/logs/).
        level: Logging level.
        console_output: Whether to also log to the colorized console.
        max_bytes: Rotation threshold for the file handlers.
        backup_count: Number of rotated backups to keep.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()  # avoid duplicate handlers when re-setup

    if log_file:
        file_handler = RotatingFileHandler(
            os.path.join(LOGS_DIR, log_file), maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(file_handler)

    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredFormatter())
        logger.addHandler(console_handler)

    # Shared error.log captures ERROR+ from every module, annotated with file:line.
    error_handler = RotatingFileHandler(
        os.path.join(LOGS_DIR, 'error.log'), maxBytes=max_bytes, backupCount=backup_count
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt=_DATE_FORMAT,
    ))
    logger.addHandler(error_handler)

    return logger
