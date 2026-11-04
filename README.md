# Conflict Escalation Monitor

Collects news on geopolitical flashpoints, scores each item for severity, and builds a daily
timeline of how often things happen and how bad they are.

**Theaters:** Iran/Israel/Gulf · Russia/Ukraine · NATO/Russia · China/Taiwan/SCS · Korean Peninsula · India/Pakistan
(edit `ww3monitor/config.py` to add more).

## Data sources (no API keys)
- **GDELT DOC 2.0 API**: article lists per theater, plus daily coverage volume (the media-attention baseline)
- **RSS**: BBC, Al Jazeera, Guardian, NYT, DW, France 24, Kyiv Independent, Times of Israel, Defense News

## Scoring
Every item gets tagged with one or more theaters (regex) and a severity from 1 to 5:

| Tier | Label | Example cues | Heat weight |
|---|---|---|---|
| 5 | Critical | nuclear use, Article 5 invoked, declaration of war, US/NATO forces attacked, ≥500 killed | 15 |
| 4 | Major escalation | ballistic/hypersonic missiles, mass barrage, mobilization, blockade, strike on nuclear site, ≥50 killed | 5 |
| 3 | Kinetic | airstrike, shelling, clashes, drone attack, casualties | 2 |
| 2 | Posturing | drills, deployments, threats, sanctions, nuclear rhetoric | 1 |
| 1 | Background | talks, ceasefire, diplomacy, aid | 0.5 |

**Heat** is the daily sum of weights per theater. The **trend** compares the last 7 days of heat
with 7 × the median daily heat over the previous 30 days: ≥1.25× is *rising*, ≤0.8× is *falling*.

## Run it
```bash
python -m ww3monitor collect             # pull latest, store in data/events.db, write data/timeline.json
python -m ww3monitor backfill --days 30  # GDELT history, about 15 minutes
python -m ww3monitor rescore             # re-apply rules after editing config.py
python -m http.server                    # open http://localhost:8000 for the dashboard
python -m pytest tests
```
Python 3.10+ and the standard library only.

## Automating it
`.github/workflows/collect.yml` runs `collect` every 3 hours and commits `data/`. Turn on GitHub
Pages (deploy from the branch root) and `index.html` becomes a live dashboard. To backfill, run the
workflow manually with `backfill_days`.

## Limitations
- Keyword severity is coarse. "Strike" can mean a labour strike, and analysis pieces score like
  the events they discuss. Use `rescore` after tuning the rules. An LLM classifier is the obvious upgrade.
- Coverage volume reflects media attention as well as events on the ground.
- English-language sources only.
