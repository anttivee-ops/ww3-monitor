"""Fetchers: GDELT DOC 2.0 API and RSS/Atom feeds. Stdlib only."""
import email.utils
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .config import CONFLICT_GDELT, RSS_FEEDS, THEATERS

UA = "Mozilla/5.0 (compatible; ww3-monitor/0.2; +https://github.com/anttivee-ops/ww3-monitor)"
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_PAUSE = 5.5  # GDELT asks for at most one request every 5 seconds


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _gdelt(params: dict, retries: int = 4) -> dict:
    url = GDELT + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(retries + 1):
        try:
            body = _get(url, timeout=60)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries:
                raise
            time.sleep(15 * 2 ** attempt)  # 15, 30, 60, 120 s
    time.sleep(GDELT_PAUSE)
    try:
        return json.loads(body)
    except json.JSONDecodeError:  # GDELT returns plain-text errors
        raise RuntimeError(body[:200].decode("utf-8", "replace"))


def _gdelt_query(theater: str) -> str:
    return f'{THEATERS[theater]["gdelt"]} {CONFLICT_GDELT} sourcelang:english'


def _gdelt_time(s: str) -> str:
    return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()


def gdelt_articles(theater: str, start: datetime | None = None, end: datetime | None = None,
                   timespan: str = "1d", retries: int = 4) -> list[dict]:
    params = {"query": _gdelt_query(theater), "mode": "artlist", "maxrecords": 250, "sort": "datedesc"}
    if start and end:
        params["startdatetime"] = start.strftime("%Y%m%d%H%M%S")
        params["enddatetime"] = end.strftime("%Y%m%d%H%M%S")
    else:
        params["timespan"] = timespan
    data = _gdelt(params, retries=retries)
    return [{
        "url": a["url"], "title": a.get("title", "").strip(), "summary": "",
        "published": _gdelt_time(a["seendate"]), "source": a.get("domain", ""),
        "origin": "gdelt", "query_theater": theater,
    } for a in data.get("articles", [])]


def gdelt_volume(theater: str, timespan: str = "3months") -> list[tuple[str, int, float]]:
    """Daily (date, article count, share-of-all-coverage) for a theater."""
    data = _gdelt({"query": _gdelt_query(theater), "mode": "timelinevolraw", "timespan": timespan})
    series = (data.get("timeline") or [{}])[0].get("data", [])
    out = []
    for p in series:
        day = p["date"][:8]
        out.append((f"{day[:4]}-{day[4:6]}-{day[6:]}", int(p["value"]), float(p.get("norm") or 0)))
    return out


def _text(el, *tags):
    for t in tags:
        found = el.find(t)
        if found is not None and (found.text or "").strip():
            return found.text.strip()
    return ""


def _parse_date(s: str) -> str:
    if not s:
        return datetime.now(timezone.utc).isoformat()
    try:
        return email.utils.parsedate_to_datetime(s).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            return datetime.now(timezone.utc).isoformat()


def rss_items(name: str, url: str) -> list[dict]:
    root = ET.fromstring(_get(url))
    atom = "{http://www.w3.org/2005/Atom}"
    rss1 = "{http://purl.org/rss/1.0/}"
    items = root.findall(".//item") + root.findall(f".//{rss1}item") + root.findall(f".//{atom}entry")
    out = []
    for it in items:
        link = _text(it, "link", f"{rss1}link")
        if not link:
            le = it.find(f"{atom}link")
            link = le.get("href", "") if le is not None else ""
        out.append({
            "url": link,
            "title": _text(it, "title", f"{rss1}title", f"{atom}title"),
            "summary": _text(it, "description", f"{rss1}description", f"{atom}summary"),
            "published": _parse_date(_text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date",
                                           f"{atom}updated", f"{atom}published")),
            "source": name, "origin": "rss", "query_theater": None,
        })
    return [o for o in out if o["url"] and o["title"]]


def all_rss() -> tuple[list[dict], dict]:
    items, errors = [], {}
    for name, url in RSS_FEEDS.items():
        try:
            items.extend(rss_items(name, url))
        except Exception as e:  # one dead feed shouldn't stop the run
            errors[name] = str(e)[:200]
    return items, errors
