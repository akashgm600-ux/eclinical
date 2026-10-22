"""CLI script to initialize database tables and verify connectivity."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.database.connection import get_engine, init_db
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser(description="Initialize database schema.")
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Optional database URL override (default: from .env or config)",
    )
    args = parser.parse_args()

    db_url = args.db_url or settings.DATABASE_URL
    print(f"[*] Connecting to database at: {db_url}")

    try:
        engine = get_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[+] Database connection successful!")

        print("[*] Creating all declarative schema tables (dim_sites, dim_subjects, fact_visits, fact_lab_results, quarantine_records, etl_pipeline_runs)...")
        init_db(engine)
        print("[+] All database tables initialized successfully!")

    except Exception as e:
        print(f"[-] Database initialization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
