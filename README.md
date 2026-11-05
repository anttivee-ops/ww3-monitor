# Conflict Escalation Monitor

Collects news on geopolitical flashpoints, scores each item for severity, and builds a daily
timeline of how often things happen and how bad they are.

**Theaters:** Iran/Israel/Gulf · Russia/Ukraine · NATO/Russia · China/Taiwan/SCS · Korean Peninsula · India/Pakistan
(edit `ww3monitor/config.py` to add more).

## Method
**Timeline (frequency and severity): GDELT 2.0 event files.** Every 15 minutes GDELT publishes
all events it has machine-coded from world news as a static file. Each event has a CAMEO code
(what happened), a QuadClass (cooperation, verbal conflict or material conflict), a Goldstein score
(-10 to +10), actor countries and a location. These are plain downloads with no search-API rate
limit, so history backfills freely. Only daily aggregates per theater are stored, plus the
8 most-reported violent events per theater and day.

Events are assigned to theaters by location and actors (`THEATER_RULES` in `config.py`), and to
tiers by CAMEO code:

| Tier | Label | CAMEO codes | Heat weight |
|---|---|---|---|
| 5 | Mass violence / WMD | 20x | 8 |
| 4 | Heavy weapons | 183 bombings, 186 assassination, 192 occupation, 194 artillery/tanks, 195 air strikes | 3 |
| 3 | Armed violence | other 18x assault, 19x fighting | 1 |
| 2 | Threats & coercion | 13 threaten, 15 force posture, 16 sanctions, 17 coerce | 0.3 |
| 1 | Verbal conflict | 10-12, 14 demand, disapprove, reject, protest | 0.1 |

**Heat** is the daily sum of event weight × (1 + log2(articles reporting the event)), so widely
covered events count more. The **trend** compares the last 7 days of heat with 7 × the median daily
heat over the previous 30 days: ≥1.25× is *rising*, ≤0.8× is *falling*. A tier counts as reached
in the last 7 days only when at least 3 events of that tier occurred on one day, because single
miscoded rows are common.

**Headlines: RSS** from BBC, Al Jazeera, Guardian, NYT, DW, France 24, Kyiv Independent and
Defense News, tagged by keyword and given a rough 1-5 keyword severity (`SEVERITY_RULES`).

## Run it
```bash
python -m ww3monitor collect                            # newest GDELT files (15 min budget) + RSS
python -m ww3monitor collect --days 90 --max-minutes 60 # catch up on 90 days of history
python -m ww3monitor rescore                            # re-apply headline rules after editing config.py
python -m http.server                    # open http://localhost:8000 for the dashboard
python -m pytest tests
```
Python 3.10+ and the standard library only.

## Automating it
`.github/workflows/collect.yml` runs every 3 hours. Each run downloads GDELT files newest-first
for up to 20 minutes and records which ones it has done, so the 90-day history fills over the
first several runs and later runs only fetch what's new. Data is committed to `data/` and the GitHub
Pages dashboard (`index.html`) updates from it.

## Limitations
- GDELT is machine-coded: expect duplicates, miscoded events and wrong locations. Tier-5
  "mass violence / WMD" in particular fires on rhetoric. Read trends against each theater's own
  baseline, not absolute counts or single events.
- Counts reflect news coverage as well as events on the ground.
- Headline severity is keyword-based and coarse.
