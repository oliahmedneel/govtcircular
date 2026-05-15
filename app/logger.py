# ========================================
# JobSite — Centralized Logging System
# ========================================
"""
Configures production-grade rotating file + console logging.
All other modules import `get_logger` from here.
"""

import os
import logging
from logging.handlers import RotatingFileHandler


def get_logger(name: str, config: dict | None = None) -> logging.Logger:
    """
    Create or retrieve a named logger with console + file handlers.

    Args:
        name: Logger name (usually __name__ of the calling module).
        config: Optional config dict with 'logging' and 'paths' keys.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # --- Defaults (used if no config provided) ---
    log_level = "INFO"
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    max_bytes = 5 * 1024 * 1024  # 5 MB
    backup_count = 5

    # --- Override from config if provided ---
    if config:
        log_cfg = config.get("logging", {})
        log_level = log_cfg.get("level", log_level)
        max_bytes = log_cfg.get("max_bytes", max_bytes)
        backup_count = log_cfg.get("backup_count", backup_count)
        paths_cfg = config.get("paths", {})
        base_dir = os.path.dirname(os.path.dirname(__file__))
        log_dir = os.path.join(base_dir, paths_cfg.get("logs", "logs"))

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # --- Formatter ---
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- Console Handler (always INFO+) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- Main Log File (rotating) ---
    main_log = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        main_log, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # --- Error-only Log File (rotating) ---
    error_log = os.path.join(log_dir, "error.log")
    error_handler = RotatingFileHandler(
        error_log, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    return logger
