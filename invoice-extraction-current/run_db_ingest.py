"""
Ingest all JSON extraction files from outputs/extractions/ into SQLite.

Usage:
    python run_db_ingest.py
"""

import json
import sys
from pathlib import Path

from core.config import OUTPUTS_DIR
from core.db import init_db, insert_extraction, source_file_exists


def main():
    print("=== Invoice DB Ingestion ===\n")

    # 1. Initialise database (creates tables if needed)
    init_db()
    print("Database initialised.\n")

    # 2. Collect JSON files
    json_files = sorted(OUTPUTS_DIR.glob("*.json"))
    if not json_files:
        print("No JSON files found in", OUTPUTS_DIR)
        sys.exit(1)

    print(f"Found {len(json_files)} JSON file(s) in {OUTPUTS_DIR}\n")

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

            if source_file_exists(source_file):
                print(f"  SKIP  {path.name}  (already in DB: {source_file})")
                skipped += 1
                continue

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
