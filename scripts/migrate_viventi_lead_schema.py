# uv run python scripts/migrate_viventi_lead_schema.py

from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatbot.core.config import config


def _normalized_db_url() -> str:
    db_url: str = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        return db_url.replace("postgres://", "postgresql://", 1)
    return db_url


def main() -> None:
    engine = sqlalchemy.create_engine(_normalized_db_url())
    sql_path = "sql/viventi_lead_schema.sql"

    with open(sql_path, encoding="utf-8") as sql_file:
        statements = [segment.strip() for segment in sql_file.read().split(";")]

    with engine.begin() as connection:
        for statement in statements:
            if statement:
                connection.execute(sqlalchemy.text(statement))

    print("Migration completed: VIVENTI lead schema ensured.")


if __name__ == "__main__":
    main()
