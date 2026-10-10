"""
clear_db.py - delete every row from every table in a SQLite database file.
The tables themselves (and the schema) are kept, and ID counters restart at 1.

    python clear_db.py                      # clears screenshot_library.db (asks first)
    python clear_db.py other.db             # clears a different file
    python clear_db.py other.db --yes       # no confirmation prompt

This only touches the database. Image files in Screenshots/ are NOT deleted.
Close the app before running it.
"""

import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / "screenshot_library.db"


def clear_all_tables(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")  # so delete order doesn't matter
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )]
        with conn:  # one transaction: all tables cleared, or none
            for table in tables:
                conn.execute('DELETE FROM "{}"'.format(table.replace('"', '""')))
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'sqlite_sequence'").fetchone():
                conn.execute("DELETE FROM sqlite_sequence")  # restart AUTOINCREMENT ids
        conn.execute("VACUUM")
        return tables
    finally:
        conn.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--yes"]
    db = Path(args[0]) if args else DEFAULT_DB

    if not db.is_file():
        raise SystemExit(f"Database not found: {db}")
    if "--yes" not in sys.argv and input(f"Delete ALL rows from every table in {db}? [y/N] ").strip().lower() != "y":
        raise SystemExit("Cancelled.")

    cleared = clear_all_tables(db)
    print(f"Cleared {len(cleared)} table(s): {', '.join(cleared)}")
