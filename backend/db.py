import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.scrapers.base import Apartment

DB_PATH = Path(__file__).parent.parent / "data" / "apartments.db"
JSON_PATH = Path(__file__).parent.parent / "data" / "apartments.json"

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apartments (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            address TEXT,
            price INTEGER,
            rooms REAL,
            size_sqm REAL,
            neighborhood TEXT,
            balcony INTEGER,
            parking INTEGER,
            furnished INTEGER,
            mamad INTEGER,
            agent INTEGER,
            image_url TEXT,
            listing_url TEXT NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )
    """)
    conn.commit()


def upsert(apt: "Apartment") -> bool:
    """Insert if new, update last_seen if existing. Returns True if this was a new listing."""
    now = _now()
    conn = _get_conn()
    existing = conn.execute("SELECT id FROM apartments WHERE id = ?", (apt.id,)).fetchone()
    if existing is None:
        conn.execute("""
            INSERT INTO apartments
            (id, source, title, address, price, rooms, size_sqm, neighborhood,
             balcony, parking, furnished, mamad, agent, image_url, listing_url,
             first_seen, last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            apt.id, apt.source, apt.title, apt.address, apt.price,
            apt.rooms, apt.size_sqm, apt.neighborhood,
            int(apt.balcony) if apt.balcony is not None else None,
            int(apt.parking) if apt.parking is not None else None,
            int(apt.furnished) if apt.furnished is not None else None,
            int(apt.mamad) if apt.mamad is not None else None,
            int(apt.agent) if apt.agent is not None else None,
            apt.image_url, apt.listing_url, now, now,
        ))
        conn.commit()
        return True
    else:
        conn.execute(
            "UPDATE apartments SET last_seen = ? WHERE id = ?", (now, apt.id)
        )
        conn.commit()
        return False


def cleanup_old(max_age_days: int) -> int:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    conn = _get_conn()
    cur = conn.execute("DELETE FROM apartments WHERE last_seen < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


def export_json() -> None:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM apartments ORDER BY first_seen DESC"
    ).fetchall()

    apartments = []
    for row in rows:
        d = dict(row)
        for bool_col in ("balcony", "parking", "furnished", "mamad", "agent"):
            val = d.get(bool_col)
            if val is not None:
                d[bool_col] = bool(val)
        apartments.append(d)

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(apartments, ensure_ascii=False, indent=2), encoding="utf-8")


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
