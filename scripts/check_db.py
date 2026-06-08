"""
Test PostgreSQL connection using DATABASE_URL from .env.
Run from project root:  python scripts/check_db.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from backend.core.config import settings
from backend.core.database import engine


def main() -> int:
    print(f"Connecting to: {settings.DATABASE_URL.split('@')[-1]}")
    try:
        with engine.begin() as conn:
            row = conn.execute(text("SELECT version()")).scalar_one()
        print("OK - connected successfully")
        print(f"Server: {row}")
        return 0
    except Exception as exc:
        print("FAILED — could not connect")
        print(f"  {type(exc).__name__}: {exc}")
        print()
        print("Checklist:")
        print("  1. Service 'postgresql-x64-18' is Running (services.msc)")
        print("  2. .env DATABASE_URL has your real postgres password")
        print("  3. URL-encode special chars in password (@ as %40, # as %23, etc.)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
