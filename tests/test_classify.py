"""Sanity checks for the rule-based classifier (synthetic headlines, not real news)."""
from ww3monitor.classify import casualties, severity, theaters_for


def test_theaters():
    assert theaters_for("IRGC fires drones toward Israel") == ["iran_israel"]
    assert "russia_ukraine" in theaters_for("Overnight attack on Kyiv")
    assert theaters_for("Pyongyang tests missile") == ["korea"]
    assert theaters_for("Local football results") == []


def test_severity_tiers():
    assert severity("Leaders resume ceasefire talks")[0] == 1
    assert severity("Navy begins drills near the strait")[0] == 2
    assert severity("Airstrike hits depot")[0] == 3
    assert severity("Ballistic missiles launched at capital")[0] == 4
    assert severity("Allies invoke Article 5 after attack")[0] == 5


def test_casualties():
    assert casualties("Strike kills at least 52 people") == 52
    assert casualties("Hundreds killed in bombardment") == 200
    assert severity("Strike kills at least 52 people")[0] == 4
    assert casualties("In 2024 talks began") == 0
