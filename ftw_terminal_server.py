#!/usr/bin/env python3
"""
Fort Worth terminal server — backs the Blend Case Manager.
Append-only SQLite store. Run with the venv active:
    source venv/bin/activate
    python3 ftw_terminal_server.py
Then find this machine's LAN IP (e.g. `ip addr` / `ipconfig`) and enter
http://<that-ip>:8090 in the Blend Case Manager's connection bar.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.oauth2 import service_account
from googleapiclient.discovery import build

DB_FILE = "ftw_terminal.db"
PORT = 8090
LOCK = threading.Lock()
GOOGLE_CREDS_FILE = "google-credentials.json"
SHEET_ID = "1siJmeWuFgVCOxK2acali-_wzY8QSJm20OLxJbP3-dfc"
CLOSED_CASES_TAB = "Closed Blend Cases"
SHEET_HEADERS = ["Case ID","Grade","Tank","TOV","Base RVP","Final RVP","Trucks","Butane (bbl)","Decision","Operator","PQ","Opened At","Closed At"]
_sheets_service = None

app = Flask(__name__)
CORS(app)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS records (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL,
  kind TEXT NOT NULL,
  case_id TEXT,
  iteration_id TEXT,
  receipt_id TEXT,
  current INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  by_user TEXT,
  data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_id ON records(id);
CREATE INDEX IF NOT EXISTS idx_kind_current ON records(kind, current);
CREATE INDEX IF NOT EXISTS idx_case ON records(case_id, current);
CREATE INDEX IF NOT EXISTS idx_iteration ON records(iteration_id, current);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def new_id(kind):
    return f"FTW-J117-{kind}-{uuid.uuid4().hex[:8]}"


def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def derive_ids(record):
    kind = record.get("kind")
    case_id = record["id"] if kind == "case" else record.get("caseId")
    iteration_id = record["id"] if kind == "iteration" else record.get("iterationId")
    receipt_id = record["id"] if kind == "receipt" else record.get("receiptId")
    return case_id, iteration_id, receipt_id


def insert_record(conn, record):
    """Insert a record (dict, already carrying id/kind/_current/etc.) as a new row."""
    case_id, iteration_id, receipt_id = derive_ids(record)
    current = 1 if record.get("_current", True) else 0
    created_at = record.get("_createdAt") or record.get("_updatedAt") or now()
    updated_at = record.get("_updatedAt")
    by_user = record.get("_by")
    conn.execute(
        "INSERT INTO records (id, kind, case_id, iteration_id, receipt_id, current, created_at, updated_at, by_user, data) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record.get("kind"), case_id, iteration_id, receipt_id,
         current, created_at, updated_at, by_user, json.dumps(record)),
    )


def fetch_current(conn, record_id):
    """Return (rowid, record_dict) for the current row with this id, or (None, None)."""
    row = conn.execute(
        "SELECT rowid, data FROM records WHERE id=? AND current=1 ORDER BY rowid DESC LIMIT 1",
        (record_id,),
    ).fetchone()
    if not row:
        return None, None
    return row["rowid"], json.loads(row["data"])


def retire_row(conn, rowid, record_dict):
    """Mark a row as no longer current, both in the indexed column and in its stored JSON."""
    record_dict["_current"] = False
    conn.execute(
        "UPDATE records SET current=0, data=? WHERE rowid=?",
        (json.dumps(record_dict), rowid),
    )


def get_sheets_service():
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service
    if not os.path.exists(GOOGLE_CREDS_FILE):
        print(f"WARNING: {GOOGLE_CREDS_FILE} not found — closed-case Sheets export disabled.")
        return None
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDS_FILE,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        _sheets_service = build("sheets", "v4", credentials=creds)
        return _sheets_service
    except Exception as e:
        print(f"WARNING: could not initialize Sheets service: {e}")
        return None


def ensure_closed_cases_tab():
    service = get_sheets_service()
    if not service:
        return
    try:
        meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if CLOSED_CASES_TAB not in existing:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={"requests": [{"addSheet": {"properties": {"title": CLOSED_CASES_TAB}}}]}
            ).execute()
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f"{CLOSED_CASES_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [SHEET_HEADERS]}
            ).execute()
    except Exception as e:
        print(f"WARNING: could not verify/create Closed Blend Cases tab: {e}")


def append_closed_case_row(case_data, measurements):
    service = get_sheets_service()
    if not service:
        return
    try:
        samples = case_data.get("samples", [])
        base_rvp = round(sum(samples) / 3, 2) if len(samples) == 3 else ""
        final_rvp = ""
        for m in measurements:
            if m.get("parameter") == "dvpe":
                final_rvp = m.get("value", "")
        trucks = case_data.get("ordered", "")
        butane = trucks * 190 if isinstance(trucks, (int, float)) else ""
        row = [
            case_data.get("caseCode", case_data.get("id", "")),
            case_data.get("grade", ""),
            case_data.get("tank", ""),
            case_data.get("tov", ""),
            base_rvp,
            final_rvp,
            trucks,
            butane,
            case_data.get("decision", ""),
            case_data.get("operator", ""),
            case_data.get("pq", ""),
            case_data.get("_createdAt", ""),
            case_data.get("_closedAt", "")
        ]
        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=f"{CLOSED_CASES_TAB}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()
    except Exception as e:
        print(f"WARNING: failed to append closed case to Sheets: {e}")


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/list")
def list_records():
    kind = request.args.get("kind")
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT data FROM records WHERE kind=? AND current=1", (kind,)
        ).fetchall()
    finally:
        conn.close()
    recs = [json.loads(r["data"]) for r in rows]
    return jsonify({"records": recs})


@app.route("/case")
def get_case():
    case_id = request.args.get("id")
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT data FROM records WHERE id=? AND current=1 ORDER BY rowid DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if not row:
            return jsonify({"error": "case not found"}), 404
        case = json.loads(row["data"])
        tree = dict(case)

        it_rows = conn.execute(
            "SELECT data FROM records WHERE kind='iteration' AND case_id=? AND current=1",
            (case_id,),
        ).fetchall()
        iterations = [json.loads(r["data"]) for r in it_rows]
        iterations.sort(key=lambda x: x.get("seq", 0))

        tree_iterations = []
        for it in iterations:
            m_rows = conn.execute(
                "SELECT data FROM records WHERE kind='measurement' AND iteration_id=? AND current=1",
                (it["id"],),
            ).fetchall()
            measurements = [json.loads(r["data"]) for r in m_rows]
            tree_iterations.append(dict(it, _measurements=measurements))
        tree["_iterations"] = tree_iterations
    finally:
        conn.close()
    return jsonify(tree)


@app.route("/create", methods=["POST"])
def create():
    body = request.get_json(force=True)
    kind = body.get("kind")
    if not kind:
        return jsonify({"error": "kind required"}), 400
    with LOCK:
        conn = get_conn()
        try:
            record = dict(body)
            record["id"] = record.get("id") or new_id(kind)
            record["_current"] = True
            record["_createdAt"] = now()
            record["_by"] = body.get("_by", "unknown")
            insert_record(conn, record)
            conn.commit()
        finally:
            conn.close()
    return jsonify(record)


@app.route("/update", methods=["POST"])
def update():
    body = request.get_json(force=True)
    target_id = body.get("id")
    if not target_id:
        return jsonify({"error": "id required"}), 400
    with LOCK:
        conn = get_conn()
        try:
            rowid, current = fetch_current(conn, target_id)
            if current is None:
                return jsonify({"error": "record not found"}), 404
            old_copy = dict(current)
            retire_row(conn, rowid, current)

            new_record = dict(old_copy)
            new_record.update({k: v for k, v in body.items() if k != "_by"})
            new_record["_current"] = True
            new_record["_updatedAt"] = now()
            new_record["_by"] = body.get("_by", "unknown")
            insert_record(conn, new_record)
            conn.commit()
        finally:
            conn.close()
    return jsonify(new_record)


@app.route("/checkout", methods=["POST"])
def checkout():
    body = request.get_json(force=True)
    case_id = body.get("id")
    device = body.get("device")
    with LOCK:
        conn = get_conn()
        try:
            rowid, case = fetch_current(conn, case_id)
            if case is None:
                return jsonify({"error": "case not found"}), 404
            if case.get("checkout"):
                return jsonify({"error": "already checked out to " + case["checkout"]["device"]}), 409

            old_copy = dict(case)
            retire_row(conn, rowid, case)

            new_case = dict(old_copy)
            new_case["_current"] = True
            new_case["checkout"] = {"device": device, "by": body.get("_by", "unknown"), "at": now()}
            new_case["status"] = "checked-out"
            insert_record(conn, new_case)
            conn.commit()
        finally:
            conn.close()
    return jsonify({"checkout": new_case["checkout"], "status": new_case["status"]})


@app.route("/checkin", methods=["POST"])
def checkin():
    body = request.get_json(force=True)
    case_id = body.get("id")
    patch = body.get("patch", {})
    with LOCK:
        conn = get_conn()
        try:
            rowid, case = fetch_current(conn, case_id)
            if case is None:
                return jsonify({"error": "case not found"}), 404

            old_copy = dict(case)
            retire_row(conn, rowid, case)

            new_case = dict(old_copy)
            new_case.update(patch)
            new_case["_current"] = True
            new_case["checkout"] = None
            new_case["status"] = "open"
            insert_record(conn, new_case)
            conn.commit()
        finally:
            conn.close()
    return jsonify({"status": new_case["status"]})


@app.route("/force-release", methods=["POST"])
def force_release():
    body = request.get_json(force=True)
    case_id = body.get("id")
    with LOCK:
        conn = get_conn()
        try:
            rowid, case = fetch_current(conn, case_id)
            if case is None:
                return jsonify({"error": "case not found"}), 404

            old_copy = dict(case)
            retire_row(conn, rowid, case)

            new_case = dict(old_copy)
            new_case["_current"] = True
            new_case["checkout"] = None
            new_case["status"] = "open"
            new_case["_forceReleasedBy"] = body.get("_by", "unknown")
            new_case["_forceReleasedAt"] = now()
            insert_record(conn, new_case)
            conn.commit()
        finally:
            conn.close()
    return jsonify({"status": new_case["status"]})


@app.route("/close", methods=["POST"])
def close():
    body = request.get_json(force=True)
    case_id = body.get("id")
    with LOCK:
        conn = get_conn()
        try:
            rowid, case = fetch_current(conn, case_id)
            if case is None:
                return jsonify({"error": "case not found"}), 404

            old_copy = dict(case)
            retire_row(conn, rowid, case)

            new_case = dict(old_copy)
            new_case["_current"] = True
            new_case["status"] = "closed"
            new_case["finalIterationId"] = body.get("finalIterationId")
            new_case["_closedAt"] = now()
            insert_record(conn, new_case)
            conn.commit()

            measurements = []
            final_iteration_id = new_case.get("finalIterationId")
            if final_iteration_id:
                m_rows = conn.execute(
                    "SELECT data FROM records WHERE kind='measurement' AND iteration_id=? AND current=1",
                    (final_iteration_id,),
                ).fetchall()
                measurements = [json.loads(r["data"]) for r in m_rows]
        finally:
            conn.close()

    append_closed_case_row(new_case, measurements)
    return jsonify({"status": "closed"})


if __name__ == "__main__":
    init_db()
    ensure_closed_cases_tab()
    app.run(host="0.0.0.0", port=PORT, debug=True)
