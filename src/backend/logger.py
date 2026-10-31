"""
Application-Wide Structured Logging Module for Agentic QE Platform.
Provides dual logging (file: data/sdlc.log, stdout) and an in-memory ring buffer
for real-time observability and live log streaming in the UI.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGS_DIR = Path(__file__).resolve().parents[2] / "data"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "sdlc.log"

# Circular buffer for last 1000 logs for real-time UI debugging
LOG_BUFFER: deque[Dict[str, Any]] = deque(maxlen=1000)


class InMemoryLogHandler(logging.Handler):
    """Stores structured log entries in an in-memory deque for the Observability API."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno,
            }
            if record.exc_info:
                entry["exception"] = self.format(record)
            LOG_BUFFER.append(entry)
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "agentic_qe") -> logging.Logger:
    """Configures application logger with file, stream, and memory buffer handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(module)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Stream Handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Memory Handler for UI Log Viewer
    memory_handler = InMemoryLogHandler()
    memory_handler.setLevel(logging.INFO)
    logger.addHandler(memory_handler)

    return logger


logger = setup_logger()


def get_recent_logs(limit: int = 150, level: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns recent log entries from the in-memory circular buffer."""
    logs = list(LOG_BUFFER)
    if level:
        level_upper = level.upper()
        logs = [l for l in logs if l.get("level") == level_upper]
    return logs[-limit:]
