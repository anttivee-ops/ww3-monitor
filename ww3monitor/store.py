"""SQLite storage with de-duplication by URL and normalised headline."""
import json
import re
import sqlite3
from pathlib import Path

from .classify import off_topic, severity, theaters_for

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE,
  title_key TEXT,
  title TEXT, summary TEXT, source TEXT, origin TEXT,
  published TEXT, day TEXT,
  theaters TEXT,          -- JSON list
  severity INTEGER, cues TEXT,
  fetched TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_events_day ON events(day);
CREATE INDEX IF NOT EXISTS ix_events_key ON events(title_key, day);
CREATE TABLE IF NOT EXISTS volume (
  theater TEXT, day TEXT, articles INTEGER, share REAL,
  PRIMARY KEY (theater, day)
);
CREATE TABLE IF NOT EXISTS runs (
  ts TEXT DEFAULT (datetime('now')), added INTEGER, errors TEXT
);
"""

_STRIP_HTML = re.compile(r"<[^>]+>")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def title_key(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return " ".join(w for w in words if len(w) > 2)[:80]


def add(db: sqlite3.Connection, item: dict) -> bool:
    title = _STRIP_HTML.sub("", item["title"]).strip()
    summary = _STRIP_HTML.sub("", item.get("summary") or "").strip()[:600]
    if off_topic(title):
        return False
    text = f"{title}. {summary}"
    theaters = theaters_for(text)
    if not theaters and item.get("query_theater"):
        theaters = [item["query_theater"]]
    if not theaters:
        return False  # not about a tracked theater
    sev, cues = severity(text)
    if item["origin"] == "rss" and sev < 2 and not cues:
        return False  # RSS item with no security signal
    day, key = item["published"][:10], title_key(title)
    if db.execute("SELECT 1 FROM events WHERE title_key=? AND day=?", (key, day)).fetchone():
        return False  # same story syndicated elsewhere
    cur = db.execute(
        "INSERT OR IGNORE INTO events(url,title_key,title,summary,source,origin,published,day,theaters,severity,cues)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (item["url"], key, title, summary, item["source"], item["origin"], item["published"], day,
         json.dumps(theaters), sev, json.dumps(cues)))
    return cur.rowcount == 1


def put_volume(db, theater: str, rows):
    db.executemany("INSERT OR REPLACE INTO volume VALUES (?,?,?,?)", [(theater, *r) for r in rows])
