"""
storage.py - file a captured screenshot into Screenshots/<Category>/ and record it in SQLite.

Public API
    init_db()                              create the database from image_repository.sql if needed
    save_screenshot(path, metadata) -> dict   the function main.py calls (see below)
    resolve_path(file_path) -> Path        turn a stored file_path back into a real path

save_screenshot(path, metadata)
    path      the PNG that capture.py saved (normally in Screenshots/_pending/)
    metadata  the dict returned by ai_analyses.analyse_screenshot():
                  title, category, tags, description, ai_failed, error
    returns   the same field names, plus:
                  id         database row id
                  file_path  path stored in the database (relative to this folder, forward slashes)
                  abs_path   absolute path of the final saved image

Safety guarantees
    - The original in _pending is only removed AFTER the copy is verified and the database
      row is committed. If anything fails, it is left where it was and an exception is raised.
    - An existing file is never overwritten (a numeric suffix is added if the name is taken).
    - Folder names only ever come from categories.CATEGORIES (unknown -> "Other"), so a bad
      AI answer can't create odd folders or escape the Screenshots directory.
    - Importing this module has no side effects (no folders, no database access).
"""

import sqlite3
import shutil
import threading
from pathlib import Path

from categories import CATEGORIES, FALLBACK_CATEGORY

BASE_DIR = Path(__file__).resolve().parent
SCREENSHOTS_DIR = BASE_DIR / "Screenshots"
PENDING_DIR = SCREENSHOTS_DIR / "_pending"        # same place capture.py writes to

# NOTE: deliberately NOT the sample "image_repository.db" (that file holds demo rows for
# categories like Nature/Cities and images that don't exist). Same schema, fresh file.
DB_PATH = BASE_DIR / "screenshot_library.db"
SCHEMA_PATH = BASE_DIR / "image_repository.sql"

MAX_TITLE_CHARS = 255
MAX_TAG_CHARS = 100

_init_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the database from image_repository.sql if it has no tables yet. Safe to repeat."""
    with _init_lock:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        conn = connect()
        try:
            has_images = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'images'"
            ).fetchone()
            if not has_images:
                conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        finally:
            conn.close()


def resolve_path(file_path):
    """Stored file_path (relative to this folder, or absolute) -> absolute Path."""
    p = Path(file_path)
    return p if p.is_absolute() else BASE_DIR / p


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------
def save_screenshot(path, metadata):
    """File one screenshot and record it. Raises on failure (original is left untouched)."""
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"screenshot not found: {src}")

    meta = _normalise(metadata, src)
    init_db()

    dest_dir = SCREENSHOTS_DIR / meta["category"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = _copy_without_overwrite(src, dest_dir)
    rel_path = dest.relative_to(BASE_DIR).as_posix()

    try:
        image_id = _insert_record(meta, rel_path)
    except Exception:
        dest.unlink(missing_ok=True)   # undo our copy; the original is still safe in _pending
        raise

    _remove_pending_original(src)

    return {
        "id": image_id,
        "title": meta["title"],
        "category": meta["category"],
        "tags": meta["tags"],
        "description": meta["description"],
        "ai_failed": meta["ai_failed"],
        "error": meta["error"],
        "file_path": rel_path,
        "abs_path": str(dest),
    }


# ---------------------------------------------------------------------------
# Metadata clean-up (one place that defines the field names/types we accept)
# ---------------------------------------------------------------------------
def _normalise(metadata, src):
    data = metadata if isinstance(metadata, dict) else {}

    title = " ".join(str(data.get("title") or "").split())[:MAX_TITLE_CHARS]
    if not title:
        title = src.stem.replace("_", " ").replace("-", " ").strip() or "Untitled screenshot"

    wanted = str(data.get("category") or "").strip().lower()
    category = next((c for c in CATEGORIES if c.lower() == wanted), FALLBACK_CATEGORY)

    tags_in = data.get("tags") or []
    if isinstance(tags_in, str):
        tags_in = tags_in.split(",")
    tags, seen = [], set()
    for item in tags_in if isinstance(tags_in, (list, tuple)) else []:
        tag = " ".join(str(item).split()).lower()[:MAX_TAG_CHARS].strip()
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)

    return {
        "title": title,
        "category": category,
        "tags": tags,
        "description": str(data.get("description") or ""),
        "ai_failed": bool(data.get("ai_failed")),
        "error": data.get("error"),
    }


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------
def _copy_without_overwrite(src, dest_dir):
    """Copy src into dest_dir using a name that is not taken. Never overwrites."""
    for n in range(1000):
        name = src.name if n == 0 else f"{src.stem}_{n}{src.suffix}"
        candidate = dest_dir / name
        try:
            out = open(candidate, "xb")          # "x" = fail if the file already exists
        except FileExistsError:
            continue
        try:
            with out, open(src, "rb") as inp:
                shutil.copyfileobj(inp, out)
            if candidate.stat().st_size != src.stat().st_size:
                raise OSError(f"copy verification failed for {candidate}")
        except Exception:
            candidate.unlink(missing_ok=True)    # remove only the partial file we created
            raise
        return candidate
    raise FileExistsError(f"could not find a free file name for {src.name} in {dest_dir}")


def _remove_pending_original(src):
    """Delete the original only if it is in _pending (never touch any other file)."""
    try:
        if src.resolve().parent == PENDING_DIR.resolve():
            src.unlink()
    except OSError:
        pass   # the final copy is safe; a leftover pending file is harmless


# ---------------------------------------------------------------------------
# Database writes (one transaction: either everything is stored or nothing is)
# ---------------------------------------------------------------------------
def _insert_record(meta, rel_path):
    conn = connect()
    conn.isolation_level = None          # we manage the transaction ourselves
    try:
        conn.execute("BEGIN IMMEDIATE")  # one writer at a time, so no duplicate categories/tags
        try:
            row = conn.execute(
                "SELECT id FROM categories WHERE name = ? AND parent_id IS NULL",
                (meta["category"],),
            ).fetchone()
            if row:
                category_id = row[0]
            else:
                category_id = conn.execute(
                    "INSERT INTO categories (name, parent_id) VALUES (?, NULL)",
                    (meta["category"],),
                ).lastrowid

            image_id = conn.execute(
                "INSERT INTO images (title, file_path, category_id) VALUES (?, ?, ?)",
                (meta["title"], rel_path, category_id),
            ).lastrowid

            for tag in meta["tags"]:
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                tag_id = conn.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()[0]
                conn.execute(
                    "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                    (image_id, tag_id),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return image_id
    finally:
        conn.close()
