#!/usr/bin/env python3
"""
One-time migration: ftw_terminal_data.json -> ftw_terminal.db (SQLite).

Run once, before starting the server for the first time on data that
predates the SQLite storage backend:
    python3 migrate_json_to_sqlite.py
"""
import json
import os
import sys

from ftw_terminal_server import DB_FILE, get_conn, init_db, insert_record

JSON_FILE = "ftw_terminal_data.json"


def main():
    if not os.path.exists(JSON_FILE):
        print(f"No {JSON_FILE} found — nothing to migrate.")
        return
    if os.path.exists(DB_FILE):
        print(f"{DB_FILE} already exists — refusing to overwrite. "
              f"Remove it first if you want to re-run the migration.")
        sys.exit(1)

    with open(JSON_FILE) as f:
        db = json.load(f)
    records = db.get("records", [])

    init_db()
    conn = get_conn()
    try:
        for record in records:
            insert_record(conn, record)
        conn.commit()
    finally:
        conn.close()

    print(f"Migrated {len(records)} record(s) from {JSON_FILE} into {DB_FILE}.")


if __name__ == "__main__":
    main()
