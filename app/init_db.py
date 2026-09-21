"""Create every table declared in app/models.py and load the seed data.

Run from the repo root:   python -m app.init_db

Safe to run again: create_all only adds tables that are missing, and seed() only inserts when a table is empty.
Use it after adding a new model (e.g. Claim) so the table exists before you call the API.
"""
import sqlite3

from sqlmodel import Session

from app.db import DATABASE_URL, create_db_and_tables, engine
from app.seed import seed


def main() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed(session)

    print(f"Database: {DATABASE_URL}")
    if DATABASE_URL.startswith("sqlite"):
        path = DATABASE_URL.split("sqlite:///", 1)[1]
        with sqlite3.connect(path) as conn:
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                (count,) = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
                print(f"  {name:<10} {count:>3} rows")


if __name__ == "__main__":
    main()
