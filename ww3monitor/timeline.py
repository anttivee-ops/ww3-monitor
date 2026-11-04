"""Aggregate stored events into a daily timeline + escalation trend, export JSON."""
import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .config import SEVERITY_LABEL, SEVERITY_WEIGHT, THEATERS


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def build(db, days: int = 90) -> dict:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    day_list = list(_days(start, end))

    agg = {t: defaultdict(lambda: {"events": 0, "sev": [0] * 5, "heat": 0.0}) for t in THEATERS}
    for day, theaters, sev in db.execute(
            "SELECT day, theaters, severity FROM events WHERE day >= ?", (start.isoformat(),)):
        for t in json.loads(theaters):
            if t in agg:
                a = agg[t][day]
                a["events"] += 1
                a["sev"][sev - 1] += 1
                a["heat"] += SEVERITY_WEIGHT[sev]

    vol = defaultdict(dict)
    for t, day, n, share in db.execute("SELECT theater, day, articles, share FROM volume WHERE day >= ?",
                                       (start.isoformat(),)):
        vol[t][day] = (n, share)

    series, trend = {}, {}
    for t in THEATERS:
        rows = []
        for d in day_list:
            a = agg[t].get(d, {"events": 0, "sev": [0] * 5, "heat": 0.0})
            n = a["events"]
            rows.append({
                "day": d, "events": n, "by_sev": a["sev"], "heat": round(a["heat"], 1),
                "sev_max": max((i + 1 for i, c in enumerate(a["sev"]) if c), default=0),
                "sev_avg": round(sum((i + 1) * c for i, c in enumerate(a["sev"])) / n, 2) if n else 0,
                "volume": vol[t].get(d, (None, None))[0],
                "share": vol[t].get(d, (None, None))[1],
            })
        series[t] = rows
        heat = [r["heat"] for r in rows]
        last7 = sum(heat[-7:])
        base = heat[-37:-7]
        baseline = statistics.median(base) * 7 if base and any(base) else None
        ratio = round(last7 / baseline, 2) if baseline else None
        trend[t] = {
            "heat_7d": round(last7, 1), "baseline_7d": round(baseline, 1) if baseline else None,
            "ratio": ratio,
            "direction": None if ratio is None else ("rising" if ratio >= 1.25 else "falling" if ratio <= 0.8 else "steady"),
            "max_sev_7d": max((r["sev_max"] for r in rows[-7:]), default=0),
        }

    top = [{
        "day": d, "published": p, "title": ti, "url": u, "source": s,
        "theaters": json.loads(th), "severity": sev, "cues": json.loads(c),
    } for d, p, ti, u, s, th, sev, c in db.execute(
        "SELECT day, published, title, url, source, theaters, severity, cues FROM events "
        "WHERE day >= ? AND severity >= 3 ORDER BY severity DESC, published DESC LIMIT 400",
        ((end - timedelta(days=30)).isoformat(),))]
    latest = [{
        "day": d, "published": p, "title": ti, "url": u, "source": s,
        "theaters": json.loads(th), "severity": sev, "cues": json.loads(c),
    } for d, p, ti, u, s, th, sev, c in db.execute(
        "SELECT day, published, title, url, source, theaters, severity, cues FROM events "
        "ORDER BY published DESC LIMIT 150")]
    run = db.execute("SELECT ts, added, errors FROM runs ORDER BY ts DESC LIMIT 1").fetchone()

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_run": {"ts": run[0], "added": run[1], "errors": json.loads(run[2] or "{}")} if run else None,
        "total_events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        "theaters": {k: v["label"] for k, v in THEATERS.items()},
        "severity_labels": SEVERITY_LABEL, "severity_weights": SEVERITY_WEIGHT,
        "days": day_list, "series": series, "trend": trend,
        "top_events": top, "latest": latest,
    }
