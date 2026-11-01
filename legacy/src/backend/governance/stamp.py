from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MetadataStamper:
    """
    Implements CTL-DOC-02 (Metadata Stamping & Provenance Tracking).
    Stamps immutable frontmatter and provenance metadata into Markdown, JSON, and HTML artifacts.
    """

    @staticmethod
    def stamp_markdown(content: str, doc_id: str, mode: str = "autonomous", source_commit: str = "main") -> str:
        """Prepends or updates YAML frontmatter with provenance tracking metadata."""
        if content.startswith("---"):
            # Check if created_at is already present
            fm_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
            if fm_match:
                fm_text = fm_match.group(1)
                if "created_at:" in fm_text:
                    return content
                # Insert provenance metadata into existing front matter
                new_fm = (
                    f"doc_id: {doc_id}\n"
                    f"created_at: {now_iso()}\n"
                    f"created_by: agentic-qe v1.4.0\n"
                    f"mode: {mode}\n"
                    f"source_commit: {source_commit}\n"
                    + fm_text
                )
                return f"---\n{new_fm}\n---\n" + content[fm_match.end():]

        frontmatter = (
            f"---\n"
            f"doc_id: {doc_id}\n"
            f"created_at: {now_iso()}\n"
            f"created_by: agentic-qe v1.4.0\n"
            f"mode: {mode}\n"
            f"source_commit: {source_commit}\n"
            f"---\n\n"
        )
        return frontmatter + content

    @staticmethod
    def stamp_json(data: Dict[str, Any], doc_id: str, mode: str = "autonomous", source_commit: str = "main") -> Dict[str, Any]:
        """Embeds provenance metadata into JSON dictionaries."""
        if "_meta" not in data:
            data["_meta"] = {
                "doc_id": doc_id,
                "created_at": now_iso(),
                "created_by": "agentic-qe v1.4.0",
                "mode": mode,
                "source_commit": source_commit,
            }
        return data

    @staticmethod
    def stamp_html(html: str, doc_id: str, mode: str = "autonomous", source_commit: str = "main") -> str:
        """Injects HTML comment metadata after doctype."""
        if "agentic-qe metadata" in html:
            return html
        stamp = (
            f"<!-- agentic-qe metadata\n"
            f"doc_id: {doc_id}\n"
            f"created_at: {now_iso()}\n"
            f"created_by: agentic-qe v1.4.0\n"
            f"mode: {mode}\n"
            f"source_commit: {source_commit}\n"
            f"-->\n"
        )
        if html.startswith("<!DOCTYPE html>"):
            return "<!DOCTYPE html>\n" + stamp + html[len("<!DOCTYPE html>"):].lstrip()
        return stamp + html
