"""
Ingest all JSON extraction files from outputs/extractions/ into SQLite.

Usage:
    python run_db_ingest.py
    python run_db_ingest.py --force  # Re-ingest existing records

FIXED: Bug #25 — Added startup count validation
"""

import json
import logging
import sys
from pathlib import Path

from core.config import OUTPUTS_DIR
from core.db import init_db, insert_extraction, source_file_exists, _get_session
from core.db import Invoice
from sqlalchemy import func

logger = logging.getLogger(__name__)


def main():
    print("=== Invoice DB Ingestion ===\n")
    
    # Check for --force flag
    force_reingest = "--force" in sys.argv

    # 1. Initialise database (creates tables if needed)
    init_db()
    print("Database initialised.\n")

    # 2. Collect JSON files
    json_files = sorted(OUTPUTS_DIR.glob("*.json"))
    if not json_files:
        print("No JSON files found in", OUTPUTS_DIR)
        sys.exit(1)

    print(f"Found {len(json_files)} JSON file(s) in {OUTPUTS_DIR}\n")
    
    # FIXED: Bug #25 — Startup count validation
    session = _get_session()
    db_count = session.query(func.count(Invoice.id)).scalar()
    json_count = len(json_files)
    
    if db_count < json_count * 0.95 and not force_reingest:
        logger.error(
            "INGESTION GAP DETECTED: DB has %d invoices but %d JSON files exist (%.1f%% coverage)",
            db_count, json_count, 100.0 * db_count / json_count
        )
        print(f"⚠️  WARNING: Database has only {db_count} invoices but {json_count} JSON files exist")
        print(f"   Coverage: {100.0 * db_count / json_count:.1f}% (expect >= 95%)")
        print(f"   This indicates incomplete ingestion.")
        print(f"   Use --force flag to re-ingest all files.\n")
    
    if force_reingest:
        print("🔄 FORCE MODE: Will overwrite existing records\n")

    inserted = 0
    skipped = 0
    failed = 0

    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Derive source_file for duplicate check
            source_file = (data.get("metadata") or {}).get("source_file", "")
            if not source_file:
                print(f"  SKIP  {path.name}  (no metadata.source_file)")
                skipped += 1
                continue

            if source_file_exists(source_file) and not force_reingest:
                print(f"  SKIP  {path.name}  (already in DB: {source_file})")
                skipped += 1
                continue
            
            # FIXED: Bug #25 — Force mode deletes existing before re-inserting
            if force_reingest and source_file_exists(source_file):
                session.query(Invoice).filter_by(source_file=source_file).delete()
                session.commit()

            insert_extraction(data)
            print(f"  OK    {path.name}  -> {source_file}")
            inserted += 1

        except Exception as exc:
            print(f"  FAIL  {path.name}  ({exc})")
            failed += 1

    # 3. Summary
    print(f"\n--- Summary ---")
    print(f"  Inserted : {inserted}")
    print(f"  Skipped  : {skipped}")
    print(f"  Failed   : {failed}")
    print(f"  Total    : {len(json_files)}")


if __name__ == "__main__":
    main()
