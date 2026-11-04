"""Theater tagging and rule-based severity scoring."""
import re

from .config import CASUALTY_FLOORS, SEVERITY_RULES, THEATERS

_THEATER_RX = {k: [re.compile(p, re.I) for p in v["patterns"]] for k, v in THEATERS.items()}
_SEV_RX = {lvl: [re.compile(p, re.I) for p in pats] for lvl, pats in SEVERITY_RULES.items()}

_NUM_WORDS = {"dozens": 24, "scores": 40, "hundreds": 200, "thousands": 2000}
_CASUALTY_RX = [
    re.compile(r"\b(?:kill(?:s|ed|ing)?|dead|deaths?|death toll)\D{0,25}?(?:at least |more than |over |nearly )?(\d[\d,]*|dozens|scores|hundreds|thousands)\b", re.I),
    re.compile(r"\b(\d[\d,]*|dozens|scores|hundreds|thousands)\s+(?:people |civilians |soldiers |troops )?(?:were |are )?(?:killed|dead|die[ds]?)\b", re.I),
]


def theaters_for(text: str) -> list[str]:
    return [k for k, rxs in _THEATER_RX.items() if any(r.search(text) for r in rxs)]


def casualties(text: str) -> int:
    best = 0
    for rx in _CASUALTY_RX:
        for m in rx.finditer(text):
            raw = m.group(1).lower()
            n = _NUM_WORDS.get(raw) or int(raw.replace(",", "") or 0)
            if n < 100000:  # ignore years / large unrelated numbers
                best = max(best, n)
    return best


def severity(text: str) -> tuple[int, list[str]]:
    """Return (severity 1-5, matched cue phrases)."""
    level, cues = 0, []
    for lvl in sorted(_SEV_RX, reverse=True):
        hits = [m.group(0) for r in _SEV_RX[lvl] if (m := r.search(text))]
        if hits:
            if level == 0:
                level = lvl
            cues.extend(hits)
    killed = casualties(text)
    for minimum, floor in CASUALTY_FLOORS:
        if killed >= minimum:
            level = max(level, floor)
            cues.append(f"~{killed} killed")
            break
    return max(level, 1), cues[:6]
