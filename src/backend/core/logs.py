"""Daily JSON-lines application log: data/logs/app-YYYY-MM-DD.jsonl.

One line per API request and per warning or error. A new day starts a new file, so no file is ever renamed
(an open file cannot be renamed on Windows). Each line is written and closed, so retention can delete an old file at any time.
Every value passes redact(). Request bodies, query strings, cookies, and usernames are never given to this module.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import date, datetime, timedelta, timezone

from backend import config
from backend.core.security import redact

NAME = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.jsonl$")
IDS = ("request_id", "run_id", "stage", "agent", "error_id")  # attached to a record with extra={"fields": {...}} where known


def today() -> date:
    return datetime.now(timezone.utc).date()


def file_for(day: date):
    return config.LOGS / f"app-{day.isoformat()}.jsonl"


def prune(keep_days: int, now: date | None = None) -> list[str]:
    """Delete log files whose date in the NAME is older than keep_days. Nothing else in the folder is touched."""
    removed = []
    oldest = (now or today()) - timedelta(days=keep_days)
    for path in config.LOGS.iterdir() if config.LOGS.exists() else []:
        match = NAME.match(path.name)
        if match and path.is_file() and date.fromisoformat(match.group(1)) < oldest:
            try:
                path.unlink()
                removed.append(path.name)
            except OSError:
                pass  # in use or already gone: the next day's prune tries again
    return removed


class DailyJsonHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO)
        self._day: date | None = None

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING and record.name != "aqe.request":
            return  # whatever the root level is set to, only requests are kept below warning
        try:
            day = today()
            if day != self._day:
                self._day = day
                config.LOGS.mkdir(parents=True, exist_ok=True)
                prune(config.LOG_RETENTION_DAYS, day)
            fields = getattr(record, "fields", {}) or {}
            line = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"), "level": record.levelname, "logger": record.name,
                    "message": redact(record.getMessage()), **{k: redact(str(v)) if isinstance(v, str) else v for k, v in fields.items()}}
            with self.lock, file_for(day).open("a", encoding="utf-8") as out:
                out.write(json.dumps(line, default=str) + "\n")
        except Exception:  # noqa: BLE001 - logging must never break a request; the console handler still reports it
            self.handleError(record)


_install_lock = threading.Lock()


def install() -> None:
    """Requests are logged at INFO; any other logger writes only warnings and errors. Safe to call twice."""
    with _install_lock:
        root = logging.getLogger()
        if not any(isinstance(h, DailyJsonHandler) for h in root.handlers):
            root.addHandler(DailyJsonHandler())
        logging.getLogger("aqe.request").setLevel(logging.INFO)
        if root.level == logging.NOTSET or root.level > logging.WARNING:
            root.setLevel(logging.WARNING)
