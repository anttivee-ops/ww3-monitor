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
from .classify import severity, theaters_for
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


def backfill(db, days: int):
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    for t in THEATERS:
        try:
            store.put_volume(db, t, sources.gdelt_volume(t))
        except Exception as e:
            print(f"  ! volume {t}: {e}")
        for i in range(days, 0, -1):
            s = end - timedelta(days=i)
            try:
                n = sum(store.add(db, a) for a in sources.gdelt_articles(t, s, s + timedelta(days=1)))
                print(f"{t} {s.date()}: +{n}")
            except Exception as e:
                print(f"  ! {t} {s.date()}: {e}")
            db.commit()


def rescore(db):
    rows = db.execute("SELECT id, title, summary, theaters FROM events").fetchall()
    for id_, title, summary, th in rows:
        text = f"{title}. {summary}"
        sev, cues = severity(text)
        new_th = theaters_for(text) or json.loads(th)
        db.execute("UPDATE events SET severity=?, cues=?, theaters=? WHERE id=?",
                   (sev, json.dumps(cues), json.dumps(new_th), id_))
    db.commit()
    print(f"rescored {len(rows)} events")


def main():
    p = argparse.ArgumentParser(prog="ww3monitor")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--no-gdelt", action="store_true")
    c.add_argument("--no-rss", action="store_true")
    b = sub.add_parser("backfill")
    b.add_argument("--days", type=int, default=30)
    sub.add_parser("export")
    sub.add_parser("rescore")
    args = p.parse_args()

    db = store.connect(DB)
    if args.cmd == "collect":
        collect(db, gdelt=not args.no_gdelt, rss=not args.no_rss)
    elif args.cmd == "backfill":
        backfill(db, args.days)
    elif args.cmd == "rescore":
        rescore(db)
    export(db)


if __name__ == "__main__":
    main()
