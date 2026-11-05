"""Aggregate stored data into the dashboard's timeline.json.

Series (frequency, severity, heat, trend) come from GDELT coded events.
The headline list comes from RSS items scored by keyword rules.
"""
import json
import statistics
from datetime import datetime, timedelta, timezone

from .config import EVENT_TIER_LABEL, EVENT_TIER_WEIGHT, SEVERITY_LABEL, THEATERS
from .gdelt_events import SCHEMA, describe


def build(db, days: int = 90) -> dict:
    db.executescript(SCHEMA)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    day_list = [(start + timedelta(days=i)).isoformat() for i in range(days)]

    totals = {d: (n, c) for d, n, c in db.execute(
        "SELECT day, events, conflict FROM gdelt_totals WHERE day >= ?", (start.isoformat(),))}
    daily = {}
    for row in db.execute("SELECT theater, day, t1, t2, t3, t4, t5, heat, goldstein, articles "
                          "FROM gdelt_daily WHERE day >= ?", (start.isoformat(),)):
        daily[(row[0], row[1])] = row[2:]

    series, trend = {}, {}
    for t in THEATERS:
        rows = []
        for d in day_list:
            t1, t2, t3, t4, t5, heat, gold, arts = daily.get((t, d), (0, 0, 0, 0, 0, 0.0, 0.0, 0))
            tiers = [t1, t2, t3, t4, t5]
            n = sum(tiers)
            total = totals.get(d, (0, 0))[0]
            rows.append({
                "day": d, "events": n, "by_sev": tiers, "heat": round(heat, 1),
                "violent": t3 + t4 + t5,
                "goldstein": round(gold / n, 2) if n else None,
                # share of all GDELT events that day, so slow news days don't look like de-escalation
                "share": round(1000 * n / total, 2) if total else None,
                "has_data": d in totals,
            })
        series[t] = rows
        covered = [r for r in rows if r["has_data"]]
        heat = [r["heat"] for r in covered]
        last7 = sum(heat[-7:])
        base = heat[-37:-7]
        baseline = statistics.median(base) * 7 if len(base) >= 14 and any(base) else None
        ratio = round(last7 / baseline, 2) if baseline else None
        max_tier = 0
        for r in covered[-7:]:
            # Need several reports before a tier counts as "reached" (single miscoded rows are common)
            for i in range(4, -1, -1):
                if r["by_sev"][i] >= 3:
                    max_tier = max(max_tier, i + 1)
                    break
        trend[t] = {
            "heat_7d": round(last7, 1), "baseline_7d": round(baseline, 1) if baseline else None,
            "ratio": ratio,
            "direction": None if ratio is None else ("rising" if ratio >= 1.25 else "falling" if ratio <= 0.8 else "steady"),
            "max_sev_7d": max_tier,
        }

    top = [{
        "theater": t, "day": d, "url": u, "severity": tier, "what": describe(code),
        "actor1": a1, "actor2": a2, "location": loc, "articles": arts,
    } for t, d, u, tier, code, a1, a2, loc, arts in db.execute(
        "SELECT theater, day, url, tier, code, actor1, actor2, location, articles FROM gdelt_top "
        "WHERE day >= ? ORDER BY day DESC, tier DESC, articles DESC", ((end - timedelta(days=30)).isoformat(),))]

    headlines = [{
        "day": d, "published": p, "title": ti, "url": u, "source": s,
        "theaters": json.loads(th), "severity": sev, "cues": json.loads(c),
    } for d, p, ti, u, s, th, sev, c in db.execute(
        "SELECT day, published, title, url, source, theaters, severity, cues FROM events "
        "WHERE day >= ? ORDER BY published DESC LIMIT 400", ((end - timedelta(days=30)).isoformat(),))]

    run = db.execute("SELECT ts, added, errors FROM runs ORDER BY ts DESC LIMIT 1").fetchone()
    files = dict(db.execute("SELECT status, COUNT(*) FROM gdelt_files GROUP BY status").fetchall())
    covered_days = [d for d in day_list if d in totals]

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "last_run": {"ts": run[0], "added": run[1], "errors": json.loads(run[2] or "{}")} if run else None,
        "coverage": {"files_ok": files.get("ok", 0), "files_missing": files.get("missing", 0),
                     "first_day": covered_days[0] if covered_days else None,
                     "days_with_data": len(covered_days),
                     "events_coded": sum(n for n, _ in totals.values())},
        "total_events": sum(r["events"] for rows in series.values() for r in rows),
        "theaters": {k: v["label"] for k, v in THEATERS.items()},
        "severity_labels": EVENT_TIER_LABEL, "severity_weights": EVENT_TIER_WEIGHT,
        "headline_labels": SEVERITY_LABEL,
        "days": day_list, "series": series, "trend": trend,
        "top_events": top, "headlines": headlines,
    }
