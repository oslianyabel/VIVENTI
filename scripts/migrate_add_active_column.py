"""Migration: add 'active' column to messages table.

The schema.py defines this column but it is missing from existing databases
created before it was added.  Safe to run multiple times (IF NOT EXISTS).

# uv run python scripts/migrate_add_active_column.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatbot.core.config import config


def _normalized_db_url() -> str:
    db_url: str = config.DATABASE_URL  # type: ignore[attr-defined]
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def main() -> None:
    engine = sqlalchemy.create_engine(_normalized_db_url())

    statement = (
        "ALTER TABLE messages "
        "ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;"
    )

    with engine.begin() as connection:
        connection.execute(sqlalchemy.text(statement))

    print(
        "Migration completed: column 'active' added to 'messages' table (or already existed)."
    )


if __name__ == "__main__":
    main()
