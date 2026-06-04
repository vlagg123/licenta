import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from contextlib import contextmanager

from app.config import DATABASE_PATH
from app.models import Event


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id      INTEGER NOT NULL,
                zone         TEXT    NOT NULL,
                event_type   TEXT    NOT NULL,
                description  TEXT    NOT NULL,
                risk_score   INTEGER DEFAULT 0,
                timestamp    TEXT    NOT NULL,
                acknowledged INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id     INTEGER NOT NULL,
                temperature REAL,
                humidity    REAL,
                pressure    REAL,
                gas_value   INTEGER,
                risk_score  INTEGER,
                status      TEXT,
                timestamp   TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commands_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id   TEXT NOT NULL,
                target_node  INTEGER,
                command_type TEXT,
                payload      TEXT,
                timestamp    TEXT NOT NULL
            )
        """)


def insert_event(event: Event) -> int:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO events (node_id, zone, event_type, description, risk_score, timestamp, acknowledged) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event.node_id, event.zone, event.event_type, event.description,
             event.risk_score, event.timestamp.isoformat() + "Z", int(event.acknowledged))
        )
        return cur.lastrowid


def insert_sensor_snapshot(node_id: int, temp: float, hum: float,
                            pres: float, gas: int, risk: int,
                            status: str, ts: datetime) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO sensor_history (node_id, temperature, humidity, pressure, gas_value, risk_score, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (node_id, temp, hum, pres, gas, risk, status, ts.isoformat() + "Z")
        )


def get_events(limit: int = 100, node_id: Optional[int] = None) -> List[dict]:
    with db_cursor() as cur:
        if node_id is not None:
            cur.execute("SELECT * FROM events WHERE node_id=? ORDER BY id DESC LIMIT ?", (node_id, limit))
        else:
            cur.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cur.fetchall()]


def get_events_today_count() -> int:
    with db_cursor() as cur:
        # timestamp-urile sunt stocate in UTC, folosim data UTC nu cea locala
        today_utc = datetime.utcnow().date().isoformat()
        cur.execute("SELECT COUNT(*) FROM events WHERE timestamp LIKE ?", (f"{today_utc}%",))
        return cur.fetchone()[0]


def log_command(command_id: str, target_node: int, command_type: str, payload: dict, ts: datetime) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO commands_log (command_id, target_node, command_type, payload, timestamp) VALUES (?, ?, ?, ?, ?)",
            (command_id, target_node, command_type, json.dumps(payload), ts.isoformat() + "Z")
        )


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with db_cursor() as cur:
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with db_cursor() as cur:
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
