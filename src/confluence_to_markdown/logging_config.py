"""Logging configuration for the converter."""

import logging
import sys
from pathlib import Path

from confluence_to_markdown.config import Settings


def setup_logging(settings: Settings, verbose: bool = False) -> None:
    """Configure logging based on settings.

    Args:
        settings: Application settings containing logging config.
        verbose: If True, override level to DEBUG.
    """
    log_settings = settings.logging

    # Determine log level
    level_str = "DEBUG" if verbose else log_settings.level
    level = getattr(logging, level_str.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(log_settings.format)

    # Configure root logger for the package
    logger = logging.getLogger("confluence_to_markdown")
    logger.setLevel(level)
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if configured)
    if log_settings.file:
        log_path = Path(log_settings.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Module name (typically __name__).

    Returns:
        Logger instance for the module.
    """
    return logging.getLogger(f"confluence_to_markdown.{name}")
