"""CLI.

  python -m ww3monitor collect            # fetch latest GDELT + RSS, store, export
  python -m ww3monitor backfill --days 30 # day-by-day GDELT history (slow: ~6 req/day)
  python -m ww3monitor export             # rebuild data/timeline.json only
  python -m ww3monitor rescore            # re-apply severity rules after editing config
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import sources, store, timeline
from .classify import off_topic, severity, theaters_for
from .config import THEATERS

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "events.db"
OUT = ROOT / "data" / "timeline.json"


def export(db):
    data = timeline.build(db)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {OUT} ({data['total_events']} events total)")


def collect(db, gdelt=True, rss=True):
    added, errors = 0, {}
    if gdelt:
        for t in THEATERS:
            try:
                for a in sources.gdelt_articles(t, timespan="1d"):
                    added += store.add(db, a)
                store.put_volume(db, t, sources.gdelt_volume(t))
            except Exception as e:
                errors[f"gdelt:{t}"] = str(e)[:200]
            db.commit()
    if rss:
        items, rss_errors = sources.all_rss()
        errors.update({f"rss:{k}": v for k, v in rss_errors.items()})
        for it in items:
            added += store.add(db, it)
    db.execute("INSERT INTO runs(added, errors) VALUES (?,?)", (added, json.dumps(errors)))
    db.commit()
    print(f"added {added} events; {len(errors)} source errors")
    for k, v in errors.items():
        print(f"  ! {k}: {v}")


def backfill(db, days: int, max_minutes: float = 30):
    """Fetch GDELT history day by day. Resumable: finished (theater, day) pairs are
    remembered, and the run stops cleanly when the time budget runs out or GDELT
    keeps rate-limiting, so a later run picks up where this one left off."""
    import time
    deadline = time.monotonic() + max_minutes * 60
    db.execute("CREATE TABLE IF NOT EXISTS backfill_done (theater TEXT, day TEXT, PRIMARY KEY (theater, day))")
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    todo = [(t, end - timedelta(days=i)) for i in range(1, days + 1) for t in THEATERS]  # newest first
    done = set(db.execute("SELECT theater, day FROM backfill_done"))
    todo = [(t, s) for t, s in todo if (t, s.date().isoformat()) not in done]
    print(f"backfill: {len(todo)} theater-days left of {days * len(THEATERS)}")
    volume_done = False
    failures = 0
    for t, s in todo:
        if time.monotonic() > deadline:
            print("backfill: time budget used up; will resume next run")
            break
        if not volume_done:
            for th in THEATERS:
                try:
                    store.put_volume(db, th, sources.gdelt_volume(th))
                except Exception as e:
                    print(f"  ! volume {th}: {e}")
            volume_done = True
        try:
            n = sum(store.add(db, a) for a in sources.gdelt_articles(t, s, s + timedelta(days=1), retries=1))
            db.execute("INSERT OR IGNORE INTO backfill_done VALUES (?,?)", (t, s.date().isoformat()))
            print(f"{t} {s.date()}: +{n}")
            failures = 0
        except Exception as e:
            failures += 1
            print(f"  ! {t} {s.date()}: {e}")
            if failures >= 5:
                print("backfill: GDELT keeps failing; stopping, will resume next run")
                break
        db.commit()
    db.commit()


def rescore(db):
    rows = db.execute("SELECT id, title, summary, theaters FROM events").fetchall()
    dropped = 0
    for id_, title, summary, th in rows:
        if off_topic(title):
            db.execute("DELETE FROM events WHERE id=?", (id_,))
            dropped += 1
            continue
        text = f"{title}. {summary}"
        sev, cues = severity(text)
        new_th = theaters_for(text) or json.loads(th)
        db.execute("UPDATE events SET severity=?, cues=?, theaters=? WHERE id=?",
                   (sev, json.dumps(cues), json.dumps(new_th), id_))
    db.commit()
    print(f"rescored {len(rows) - dropped} events, dropped {dropped} off-topic")


def main():
    p = argparse.ArgumentParser(prog="ww3monitor")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--no-gdelt", action="store_true")
    c.add_argument("--no-rss", action="store_true")
    b = sub.add_parser("backfill")
    b.add_argument("--days", type=int, default=30)
    b.add_argument("--max-minutes", type=float, default=30)
    sub.add_parser("export")
    sub.add_parser("rescore")
    args = p.parse_args()

    db = store.connect(DB)
    if args.cmd == "collect":
        collect(db, gdelt=not args.no_gdelt, rss=not args.no_rss)
    elif args.cmd == "backfill":
        backfill(db, args.days, args.max_minutes)
    elif args.cmd == "rescore":
        rescore(db)
    export(db)


if __name__ == "__main__":
    main()
