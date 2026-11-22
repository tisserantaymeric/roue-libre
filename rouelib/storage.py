"""Stockage local : historique des séances (SQLite) et réglages (JSON)."""

import json
import sqlite3
import time
from pathlib import Path

XDG_DATA = Path.home() / ".local" / "share"
XDG_CONFIG = Path.home() / ".config"
DATA_DIR = XDG_DATA / "roue-libre"
CONFIG_DIR = XDG_CONFIG / "roue-libre"
DB_PATH = DATA_DIR / "historique.db"
CONFIG_PATH = CONFIG_DIR / "reglages.json"


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " ts INTEGER NOT NULL,"
        " activity TEXT NOT NULL,"
        " route_name TEXT,"
        " duration_s REAL NOT NULL,"
        " distance_m REAL NOT NULL,"
        " avg_power REAL, max_power REAL,"
        " avg_hr REAL, avg_cadence REAL,"
        " elev_gain REAL)"
    )
    return conn


def save_session(summary: dict) -> None:
    with _connect() as conn:
        conn.execute("INSERT INTO sessions (ts, activity, route_name, duration_s,"
                     " distance_m, avg_power, max_power, avg_hr, avg_cadence, elev_gain)"
                     " VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (int(summary.get("ts", time.time())),
                      summary.get("activity", "Sortie libre"),
                      summary.get("route_name", ""),
                      float(summary.get("duration_s", 0)),
                      float(summary.get("distance_m", 0)),
                      summary.get("avg_power"),
                      summary.get("max_power"),
                      summary.get("avg_hr"),
                      summary.get("avg_cadence"),
                      summary.get("elev_gain")))


def list_sessions(limit: int = 200) -> list:
    with _connect() as conn:
        rows = conn.execute("SELECT id, ts, activity, route_name, duration_s,"
                            " distance_m, avg_power, max_power, avg_hr, avg_cadence,"
                            " elev_gain FROM sessions ORDER BY ts DESC LIMIT ?",
                            (limit,)).fetchall()
    keys = ["id", "ts", "activity", "route_name", "duration_s", "distance_m",
            "avg_power", "max_power", "avg_hr", "avg_cadence", "elev_gain"]
    return [dict(zip(keys, row)) for row in rows]


def totals() -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*), IFNULL(SUM(duration_s),0),"
                           " IFNULL(SUM(distance_m),0), IFNULL(SUM(elev_gain),0)"
                           " FROM sessions").fetchone()
    return {"sessions": row[0], "duration_s": row[1],
            "distance_m": row[2], "elev_gain": row[3]}


def load_settings(defaults: dict) -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except (OSError, json.JSONDecodeError):
        stored = {}
    merged = dict(defaults)
    merged.update({k: v for k, v in stored.items() if k in defaults})
    return merged


def save_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
