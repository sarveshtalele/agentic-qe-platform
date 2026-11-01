"""Admin download of one day's application log."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.config import LOGS
from backend.core import logs
from backend.core.security import safe_path

router = APIRouter()


@router.get("/api/logs")
def download_log(date: str = ""):
    """Defaults to today. Only a real YYYY-MM-DD date is accepted, and the file is read through safe_path."""
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise HTTPException(422, "The date must be written YYYY-MM-DD")
    try:
        day = logs.date.fromisoformat(date) if date else logs.today()
    except ValueError:
        raise HTTPException(422, "That is not a real date. Use YYYY-MM-DD") from None
    path = safe_path(LOGS, logs.file_for(day).name)
    if not path.is_file():
        raise HTTPException(404, f"No log for {day.isoformat()}")
    return Response(path.read_bytes(), media_type="application/x-ndjson", headers={"Content-Disposition": f'attachment; filename="{path.name}"'})
