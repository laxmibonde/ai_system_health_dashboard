"""
database/db_manager.py
Handles SQLite database creation, insertion, and querying.
OS Concept: Persistent storage for time-series system metrics.
"""

import sqlite3
import os
from datetime import datetime

# Always store DB at project root (two levels up from database/db_manager.py)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
DB_PATH = os.path.join(_PROJECT_ROOT, "system_metrics.db")


def get_connection():
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initialize the database and create tables if they don't exist.
    OS Concept: Schema represents OS resource management data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            cpu       REAL    NOT NULL,
            memory    REAL    NOT NULL,
            disk      REAL    NOT NULL,
            net_sent  REAL    NOT NULL DEFAULT 0,
            net_recv  REAL    NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS anomalies (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            metric     TEXT NOT NULL,
            value      REAL NOT NULL,
            severity   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message    TEXT NOT NULL,
            resolved   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS top_processes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            pid         INTEGER NOT NULL,
            name        TEXT NOT NULL,
            cpu_percent REAL NOT NULL,
            mem_percent REAL NOT NULL
        );
    """)

    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def insert_metric(cpu, memory, disk, net_sent=0, net_recv=0):
    """Insert one row of system metrics."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO system_metrics (timestamp, cpu, memory, disk, net_sent, net_recv) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), cpu, memory, disk, net_sent, net_recv)
    )
    conn.commit()
    conn.close()


def insert_anomaly(metric, value, severity):
    """Log a detected anomaly."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO anomalies (timestamp, metric, value, severity) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), metric, value, severity)
    )
    conn.commit()
    conn.close()


def insert_alert(alert_type, message):
    """Log a system alert."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO alerts (timestamp, alert_type, message) VALUES (?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), alert_type, message)
    )
    conn.commit()
    conn.close()


def insert_top_processes(processes):
    """Store top N processes snapshot."""
    conn = get_connection()
    ts = datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        "INSERT INTO top_processes (timestamp, pid, name, cpu_percent, mem_percent) "
        "VALUES (?, ?, ?, ?, ?)",
        [(ts, p["pid"], p["name"], p["cpu_percent"], p["mem_percent"]) for p in processes]
    )
    conn.commit()
    conn.close()


def fetch_recent_metrics(limit=200):
    """Fetch the most recent N metric rows."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM system_metrics ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def fetch_all_metrics():
    """Fetch entire metric history for model training."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM system_metrics ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_recent_anomalies(limit=50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM anomalies ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_recent_alerts(limit=50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_top_processes_latest():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM top_processes WHERE timestamp = "
        "(SELECT MAX(timestamp) FROM top_processes)"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_metrics():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM system_metrics").fetchone()[0]
    conn.close()
    return count
