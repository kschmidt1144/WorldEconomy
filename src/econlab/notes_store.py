"""Reading notes store — the bridge between the tablet reader and this apparatus.

The `webreader` PWA writes margin notes (anchored to a chapter + heading/figure)
to Firestore, named database **worldeconomy**, collection **notes**. This module
reads/writes the same collection via the Firebase Admin SDK (Application Default
Credentials), so `econ notes` and the `econ_notes` / `econ_note_add` MCP tools can
recall and add notes from any Claude session — "summarize my Ch10 notes", etc.

Note schema (shared verbatim with the PWA):
  id, chapter, chapterTitle, anchor, anchorText, quote, body, color,
  source ("web" | "cli" | "mcp"), createdAt (epoch ms), updatedAt (epoch ms).

Graceful like the FRED key: if firebase-admin or ADC is missing, the callers
report a clear one-line reason instead of crashing.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

DATABASE = "worldeconomy"
COLLECTION = "notes"

_client: Any = None


class NotesUnavailable(RuntimeError):
    """Raised when the Firestore notes store can't be reached (missing dep / ADC)."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return "n_" + uuid.uuid4().hex[:12]


def client() -> Any:
    """Cached Firestore client for the `worldeconomy` named DB (ADC)."""
    global _client
    if _client is not None:
        return _client
    try:
        import firebase_admin
        from firebase_admin import firestore
    except ImportError as e:  # pragma: no cover - env-dependent
        raise NotesUnavailable(
            "firebase-admin is not installed (uv add firebase-admin)"
        ) from e
    try:
        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app()
        # MUST pass the named DB — firebase-admin defaults to (default) otherwise.
        _client = firestore.client(app, database_id=DATABASE)
    except Exception as e:  # ADC missing / project not set / permission
        raise NotesUnavailable(
            "could not reach Firestore 'worldeconomy' — run "
            "`gcloud auth application-default login` (project kykli-489802). "
            f"[{type(e).__name__}: {e}]"
        ) from e
    return _client


def add_note(
    *,
    chapter: str,
    body: str,
    quote: str = "",
    anchor: str = "",
    anchor_text: str = "",
    chapter_title: str = "",
    color: str = "sun",
    source: str = "mcp",
) -> dict:
    """Create a note and persist it. Returns the stored document."""
    now = _now_ms()
    note = {
        "id": new_id(),
        "chapter": chapter.strip(),
        "chapterTitle": chapter_title.strip(),
        "anchor": anchor.strip(),
        "anchorText": anchor_text.strip(),
        "quote": quote.strip(),
        "body": body.strip(),
        "color": color,
        "source": source,
        "createdAt": now,
        "updatedAt": now,
    }
    client().collection(COLLECTION).document(note["id"]).set(note)
    return note


def list_notes(chapter: str | None = None, query: str | None = None, limit: int = 200) -> list[dict]:
    """All notes (newest first), optionally filtered by chapter slug and/or a
    case-insensitive substring over quote+body. Fetch-all + filter in Python keeps
    the store index-free for a personal-scale collection."""
    docs = [d.to_dict() for d in client().collection(COLLECTION).stream()]
    if chapter:
        c = chapter.strip().lower()
        docs = [d for d in docs if (d.get("chapter", "").lower() == c or c in d.get("chapter", "").lower())]
    if query:
        q = query.lower()
        docs = [d for d in docs if q in (d.get("quote", "") + " " + d.get("body", "")).lower()]
    docs.sort(key=lambda d: d.get("updatedAt", 0), reverse=True)
    return docs[:limit]


def delete_note(note_id: str) -> bool:
    ref = client().collection(COLLECTION).document(note_id)
    if not ref.get().exists:
        return False
    ref.delete()
    return True
