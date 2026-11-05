"""GDELT 2.0 Event files: the quantitative backbone of the timeline.

GDELT publishes every machine-coded event it extracts from world news as a
zipped tab-separated file every 15 minutes:
    http://data.gdeltproject.org/gdeltv2/YYYYMMDDHHMMSS.export.CSV.zip
These are plain static downloads (no search-API rate limit), so history can be
backfilled freely. We keep only daily aggregates per theater plus a handful of
the most-covered violent events, never the raw rows.

Each event carries a CAMEO event code (what happened), a QuadClass (1-2
cooperation, 3 verbal conflict, 4 material conflict), a Goldstein score
(-10 destabilising .. +10 stabilising), actor countries (CAMEO 3-letter) and an
action location (FIPS 10-4 country code).
"""
import io
import math
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from .config import EVENT_TIER_WEIGHT, THEATER_RULES

BASE = "http://data.gdeltproject.org/gdeltv2/"
UA = "Mozilla/5.0 (compatible; ww3-monitor/0.3; +https://github.com/anttivee-ops/ww3-monitor)"

# Column indexes in the 61-column GDELT 2.0 export format
C_A1NAME, C_A1CTRY, C_A2NAME, C_A2CTRY = 6, 7, 16, 17
C_CODE, C_ROOT, C_QUAD, C_GOLD, C_ARTICLES = 26, 28, 29, 30, 33
C_GEONAME, C_GEOCTRY, C_ADDED, C_URL = 52, 53, 59, 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS gdelt_files (name TEXT PRIMARY KEY, status TEXT, rows INTEGER);
CREATE TABLE IF NOT EXISTS gdelt_daily (
  theater TEXT, day TEXT,
  t1 INTEGER DEFAULT 0, t2 INTEGER DEFAULT 0, t3 INTEGER DEFAULT 0, t4 INTEGER DEFAULT 0, t5 INTEGER DEFAULT 0,
  heat REAL DEFAULT 0, goldstein REAL DEFAULT 0, articles INTEGER DEFAULT 0,
  PRIMARY KEY (theater, day));
CREATE TABLE IF NOT EXISTS gdelt_totals (day TEXT PRIMARY KEY, events INTEGER DEFAULT 0, conflict INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS gdelt_top (
  theater TEXT, day TEXT, url TEXT, tier INTEGER, code TEXT, actor1 TEXT, actor2 TEXT,
  location TEXT, articles INTEGER, PRIMARY KEY (theater, day, url));
"""

# Readable names for the CAMEO codes that matter here (code, then base, then root).
CAMEO = {
    "10": "demand", "11": "disapprove", "12": "reject", "13": "threaten", "14": "protest",
    "138": "threaten military force", "1384": "threaten conventional attack", "1385": "threaten WMD attack",
    "15": "military posturing", "152": "raise military alert", "154": "mobilise armed forces",
    "16": "reduce relations", "163": "impose embargo or sanctions", "17": "coerce",
    "171": "seize or destroy property", "173": "arrest or detain", "18": "assault",
    "181": "abduct or take hostages", "182": "physical assault", "183": "bombing",
    "1831": "suicide bombing", "1832": "vehicle bombing", "1833": "roadside bombing",
    "185": "attempted assassination", "186": "assassination", "19": "armed clash",
    "190": "use of military force", "191": "blockade", "192": "occupy territory",
    "193": "small-arms fighting", "194": "artillery and tank fire", "195": "air strikes",
    "1951": "precision air strikes", "1952": "area bombing", "196": "ceasefire violation",
    "20": "mass violence", "201": "mass expulsion", "202": "mass killing", "203": "ethnic cleansing",
    "204": "use of WMD", "2041": "chemical or biological weapons", "2042": "nuclear weapons",
}


def describe(code: str) -> str:
    return CAMEO.get(code) or CAMEO.get(code[:3]) or CAMEO.get(code[:2]) or f"CAMEO {code}"


def tier_for(code: str, root: str) -> int:
    """Map a CAMEO code onto the 1-5 severity tiers."""
    if root == "20":
        return 5
    if code[:3] in ("183", "186", "192", "194", "195") or code[:4] in ("1951", "1952"):
        return 4
    if root in ("18", "19"):
        return 3
    if root in ("13", "15", "16", "17"):
        return 2
    return 1  # 10, 11, 12, 14: verbal conflict


def _pair(a1, a2, x, y):
    return (a1 in x and a2 in y) or (a1 in y and a2 in x)


def theaters_for(geo: str, a1: str, a2: str) -> list[str]:
    out = []
    for name, rules in THEATER_RULES.items():
        if geo in rules.get("geo", ()):
            out.append(name)
            continue
        if any(geo in g and (a1 in acts or a2 in acts) for g, acts in rules.get("geo_with_actor", ())):
            out.append(name)
            continue
        if any(_pair(a1, a2, x, y) for x, y in rules.get("pairs", ())):
            out.append(name)
    return out


def file_names(days: int, now: datetime | None = None) -> list[str]:
    """All expected export files in the window, newest first."""
    now = now or datetime.now(timezone.utc)
    latest = now - timedelta(minutes=20)  # files appear a few minutes after their slot
    latest = latest.replace(minute=latest.minute - latest.minute % 15, second=0, microsecond=0)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    names, t = [], latest
    while t >= start:
        names.append(t.strftime("%Y%m%d%H%M%S") + ".export.CSV.zip")
        t -= timedelta(minutes=15)
    return names


def _download(name: str) -> bytes | None:
    req = urllib.request.Request(BASE + name, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))
    return None


def parse(raw: bytes) -> dict:
    """Aggregate one export file. Returns per (theater, day) sums, per-day totals,
    and candidate top events."""
    daily = defaultdict(lambda: [0, 0, 0, 0, 0, 0.0, 0.0, 0])  # t1..t5, heat, goldstein, articles
    totals = defaultdict(lambda: [0, 0])
    top = {}
    rows = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    for line in text.splitlines():
        r = line.split("\t")
        if len(r) < 61:
            continue
        rows += 1
        day = f"{r[C_ADDED][:4]}-{r[C_ADDED][4:6]}-{r[C_ADDED][6:8]}"
        quad = r[C_QUAD]
        totals[day][0] += 1
        if quad not in ("3", "4"):
            continue
        totals[day][1] += 1
        theaters = theaters_for(r[C_GEOCTRY], r[C_A1CTRY], r[C_A2CTRY])
        if not theaters:
            continue
        code, root = r[C_CODE], r[C_ROOT]
        tier = tier_for(code, root)
        articles = int(r[C_ARTICLES] or 1)
        weight = EVENT_TIER_WEIGHT[tier] * (1 + math.log2(max(articles, 1)))
        gold = float(r[C_GOLD] or 0)
        for t in theaters:
            d = daily[(t, day)]
            d[tier - 1] += 1
            d[5] += weight
            d[6] += gold
            d[7] += articles
            if tier >= 3 and r[C_URL]:
                key = (t, day, r[C_URL])
                if key not in top or top[key][0] < tier or top[key][5] < articles:
                    top[key] = (tier, code, r[C_A1NAME].title(), r[C_A2NAME].title(),
                                r[C_GEONAME], articles)
    return {"daily": daily, "totals": totals, "top": top, "rows": rows}


def ingest(db, days: int = 90, max_minutes: float = 15, workers: int = 8) -> dict:
    """Download and aggregate pending export files, newest first, within a time budget."""
    db.executescript(SCHEMA)
    deadline = time.monotonic() + max_minutes * 60
    seen = {n for (n,) in db.execute("SELECT name FROM gdelt_files")}
    pending = [n for n in file_names(days) if n not in seen]
    stats = {"pending": len(pending), "done": 0, "missing": 0, "failed": 0, "rows": 0}
    print(f"gdelt events: {len(pending)} files pending in the {days}-day window")
    now = datetime.now(timezone.utc)

    def work(name):
        raw = _download(name)
        return name, (parse(raw) if raw else None)

    batch_size = workers * 4
    for i in range(0, len(pending), batch_size):
        if time.monotonic() > deadline:
            print("gdelt events: time budget used up; the rest resumes next run")
            break
        batch = pending[i:i + batch_size]
        with ThreadPoolExecutor(workers) as pool:
            futures = [pool.submit(work, n) for n in batch]
            for f in as_completed(futures):
                try:
                    name, res = f.result()
                except Exception as e:
                    stats["failed"] += 1
                    print(f"  ! {e}")
                    continue
                if res is None:
                    # Gaps exist in GDELT's archive; only give up on a slot once it's old.
                    slot = datetime.strptime(name[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                    if now - slot > timedelta(hours=6):
                        db.execute("INSERT OR REPLACE INTO gdelt_files VALUES (?,?,0)", (name, "missing"))
                    stats["missing"] += 1
                    continue
                _merge(db, res)
                db.execute("INSERT OR REPLACE INTO gdelt_files VALUES (?,?,?)", (name, "ok", res["rows"]))
                stats["done"] += 1
                stats["rows"] += res["rows"]
        db.commit()
        if stats["failed"] >= batch_size and stats["done"] == 0:
            print("gdelt events: every download is failing; stopping")
            break
    _prune_top(db)
    db.commit()
    print(f"gdelt events: {stats['done']} files ({stats['rows']:,} rows), "
          f"{stats['missing']} missing, {stats['failed']} failed")
    return stats


def _merge(db, res):
    for (t, day), d in res["daily"].items():
        db.execute(
            "INSERT INTO gdelt_daily VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(theater, day) DO UPDATE SET "
            "t1=t1+excluded.t1, t2=t2+excluded.t2, t3=t3+excluded.t3, t4=t4+excluded.t4, t5=t5+excluded.t5, "
            "heat=heat+excluded.heat, goldstein=goldstein+excluded.goldstein, articles=articles+excluded.articles",
            (t, day, *d))
    for day, (n, c) in res["totals"].items():
        db.execute("INSERT INTO gdelt_totals VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET "
                   "events=events+excluded.events, conflict=conflict+excluded.conflict", (day, n, c))
    for (t, day, url), (tier, code, a1, a2, loc, arts) in res["top"].items():
        db.execute("INSERT INTO gdelt_top VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(theater, day, url) DO UPDATE SET "
                   "articles=MAX(articles, excluded.articles), tier=MAX(tier, excluded.tier)",
                   (t, day, url, tier, code, a1, a2, loc, arts))


def _prune_top(db, keep: int = 8):
    """Keep only the most-covered violent events per theater-day."""
    db.execute("""
        DELETE FROM gdelt_top WHERE rowid IN (
          SELECT rowid FROM (
            SELECT rowid, ROW_NUMBER() OVER (PARTITION BY theater, day
                   ORDER BY tier DESC, articles DESC) AS rn FROM gdelt_top)
          WHERE rn > ?)""", (keep,))
