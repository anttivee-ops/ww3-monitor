"""RSS/Atom feed fetcher for the headline list. Stdlib only.
(GDELT coded events are handled in gdelt_events.py.)"""
import email.utils
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .config import RSS_FEEDS

UA = "Mozilla/5.0 (compatible; ww3-monitor/0.3; +https://github.com/anttivee-ops/ww3-monitor)"


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


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
