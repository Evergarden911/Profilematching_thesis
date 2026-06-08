"""
Create all SQLAlchemy tables in the database from DATABASE_URL in .env.
Run from project root:  python scripts/init_tables.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.core.database import Base, engine

if __name__ == "__main__":
    print(f"Target: {engine.url.database} on {engine.url.host}")
    Base.metadata.create_all(bind=engine)
    print("Done — tables created (create_all).")
