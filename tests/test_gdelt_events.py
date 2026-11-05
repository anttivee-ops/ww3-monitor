"""GDELT event-file parsing on a synthetic in-memory export file (not real data)."""
import io
import sqlite3
import zipfile

from ww3monitor import gdelt_events as g


def row(code, quad, a1="RUS", a2="UKR", geo="UP", articles=4, added="20261104120000", url="http://x/1"):
    r = [""] * 61
    r[g.C_A1NAME], r[g.C_A1CTRY], r[g.C_A2NAME], r[g.C_A2CTRY] = "RUSSIA", a1, "UKRAINE", a2
    r[g.C_CODE], r[g.C_ROOT], r[g.C_QUAD] = code, code[:2], quad
    r[g.C_GOLD], r[g.C_ARTICLES] = "-10", str(articles)
    r[g.C_GEONAME], r[g.C_GEOCTRY], r[g.C_ADDED], r[g.C_URL] = "Kharkiv, Ukraine", geo, added, url
    return "\t".join(r)


def zipped(lines):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.export.CSV", "\n".join(lines))
    return buf.getvalue()


def test_tiers_and_theaters():
    assert g.tier_for("1951", "19") == 4
    assert g.tier_for("193", "19") == 3
    assert g.tier_for("2042", "20") == 5
    assert g.tier_for("138", "13") == 2
    assert g.tier_for("112", "11") == 1
    assert g.theaters_for("UP", "RUS", "UKR") == ["russia_ukraine"]
    assert "iran_israel" in g.theaters_for("", "IRN", "USA")
    assert "nato_russia" in g.theaters_for("EN", "RUS", "")
    assert g.theaters_for("FR", "FRA", "DEU") == []


def test_parse_and_merge():
    raw = zipped([
        row("195", "4", url="http://x/1"),          # air strike, Russia/Ukraine
        row("193", "4", url="http://x/2"),          # small-arms fighting
        row("042", "1"),                            # cooperation: counted in totals only
        row("193", "4", a1="FRA", a2="DEU", geo="FR"),  # conflict, but no tracked theater
    ])
    res = g.parse(raw)
    assert res["rows"] == 4
    assert res["totals"]["2026-11-04"] == [4, 3]
    d = res["daily"][("russia_ukraine", "2026-11-04")]
    assert d[2] == 1 and d[3] == 1  # one tier-3, one tier-4
    assert len(res["top"]) == 2

    db = sqlite3.connect(":memory:")
    db.executescript(g.SCHEMA)
    g._merge(db, res)
    g._merge(db, res)  # a second file adds on top
    assert db.execute("SELECT t3, t4 FROM gdelt_daily").fetchone() == (2, 2)


def test_file_names_newest_first():
    names = g.file_names(1)
    assert names[0] > names[-1] and names[0].endswith("00.export.CSV.zip")
    assert len(names) >= 96
