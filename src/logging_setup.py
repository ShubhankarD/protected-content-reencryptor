"""Small, generic logging helper for attaching a file handler.

This module provides a tiny function `configure_file_logging` that ensures a
logs directory exists, attaches a RotatingFileHandler, and returns the log
file path. It intentionally avoids any product-specific logic so it can be
reused across components.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from typing import Iterable, Optional
import sys
from datetime import datetime


def configure_file_logging(logs_dir: Optional[str] = None,
                           filename: Optional[str] = None,
                           *,
                           max_bytes: int = 5 * 1024 * 1024,
                           backup_count: int = 3,
                           logger_names: Optional[Iterable[str]] = None,
                           level: str = "DEBUG") -> str:
    """Attach a rotating file handler to the given loggers (or root logger).

    - If `logger_names` is None the handler is attached to the root logger so
      all loggers will propagate to the handler by default.
    - Returns the absolute path to the log file.
    """
    if logs_dir is None:
        here = os.path.dirname(__file__)
        logs_dir = os.path.abspath(os.path.join(here, "..", "logs"))
    os.makedirs(logs_dir, exist_ok=True)

    # If no filename provided, build one from the running script name and current datetime
    if not filename:
        try:
            script_name = os.path.splitext(os.path.basename(sys.argv[0] or "script"))[0]
        except Exception:
            script_name = "script"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{script_name}_{ts}.log"

    log_path = os.path.join(logs_dir, filename)
    handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=max_bytes,
                                                   backupCount=backup_count, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))

    targets = []
    if logger_names is None:
        targets.append(logging.getLogger())
    else:
        for name in logger_names:
            targets.append(logging.getLogger(name))

    for lg in targets:
        # avoid adding duplicate handlers for same file
        already = False
        for h in lg.handlers:
            if hasattr(h, "baseFilename") and os.path.abspath(getattr(h, "baseFilename")) == os.path.abspath(log_path):
                already = True
                break
        if not already:
            lg.addHandler(handler)
        try:
            lg.setLevel(getattr(logging, level))
        except Exception:
            lg.setLevel(logging.INFO)

    # generic startup message using the root logger
    try:
        logging.getLogger().info("File logging initialized: %s", os.path.abspath(log_path))
    except Exception:
        pass

    return os.path.abspath(log_path)
