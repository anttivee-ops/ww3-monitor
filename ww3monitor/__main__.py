"""CLI.

  python -m ww3monitor collect                  # GDELT event files (newest first, resumable) + RSS, export
  python -m ww3monitor collect --days 90 --max-minutes 45   # bigger catch-up / backfill
  python -m ww3monitor export                   # rebuild data/timeline.json only
  python -m ww3monitor rescore                  # re-apply headline rules after editing config
"""
import argparse
import json
from pathlib import Path

from . import gdelt_events, sources, store, timeline
from .classify import off_topic, severity, theaters_for

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "events.db"
OUT = ROOT / "data" / "timeline.json"


def export(db):
    data = timeline.build(db)
    OUT.write_text(json.dumps(data, separators=(",", ":")))
    cov = data["coverage"]
    print(f"wrote {OUT}: {cov['days_with_data']} days of coded events, {len(data['headlines'])} headlines")


def collect(db, days: int, max_minutes: float, gdelt=True, rss=True):
    added, errors = 0, {}
    if gdelt:
        try:
            stats = gdelt_events.ingest(db, days=days, max_minutes=max_minutes)
            if stats["failed"] and not stats["done"]:
                errors["gdelt-events"] = f"{stats['failed']} downloads failed"
        except Exception as e:
            errors["gdelt-events"] = str(e)[:200]
    if rss:
        items, rss_errors = sources.all_rss()
        errors.update({f"rss:{k}": v for k, v in rss_errors.items()})
        for it in items:
            added += store.add(db, it)
    db.execute("INSERT INTO runs(added, errors) VALUES (?,?)", (added, json.dumps(errors)))
    db.commit()
    print(f"added {added} headlines; {len(errors)} source errors")
    for k, v in errors.items():
        print(f"  ! {k}: {v}")


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
    print(f"rescored {len(rows) - dropped} headlines, dropped {dropped} off-topic")


def main():
    p = argparse.ArgumentParser(prog="ww3monitor")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("collect", "backfill"):  # backfill = collect with a bigger default budget
        c = sub.add_parser(name)
        c.add_argument("--days", type=int, default=90, help="window of GDELT history to keep filled")
        c.add_argument("--max-minutes", type=float, default=15 if name == "collect" else 45)
        c.add_argument("--no-gdelt", action="store_true")
        c.add_argument("--no-rss", action="store_true")
    sub.add_parser("export")
    sub.add_parser("rescore")
    args = p.parse_args()

    db = store.connect(DB)
    if args.cmd in ("collect", "backfill"):
        collect(db, args.days, args.max_minutes, gdelt=not args.no_gdelt, rss=not args.no_rss)
    elif args.cmd == "rescore":
        rescore(db)
    export(db)


if __name__ == "__main__":
    main()
