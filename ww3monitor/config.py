"""Theaters, sources and severity rules. Edit this file to tune the monitor."""

# --- Theaters -------------------------------------------------------------
# Each theater has keyword patterns (regex, case-insensitive, matched against
# title + summary) and a GDELT DOC API query used for article lists and the
# volume timeline.
THEATERS = {
    "iran_israel": {
        "label": "Iran / Israel / Gulf",
        "patterns": [
            r"\biran(ian)?s?\b", r"\btehran\b", r"\birgc\b", r"\bisrael(i)?s?\b",
            r"\bidf\b", r"\bhezbollah\b", r"\bhouthis?\b", r"\bgaza\b", r"\bhamas\b",
            r"\blebanon\b", r"\byemen\b", r"\bhormuz\b", r"\bkhamenei\b", r"\bnetanyahu\b",
        ],
        "gdelt": '(Iran OR Israel OR Hezbollah OR Houthi OR IRGC OR Hormuz)',
    },
    "russia_ukraine": {
        "label": "Russia / Ukraine",
        "patterns": [
            r"\bukrain(e|ian)s?\b", r"\bkyiv\b", r"\bkiev\b", r"\bzelensk(y|iy)\b",
            r"\bdonbas+\b", r"\bdonetsk\b", r"\bkharkiv\b", r"\bzaporizhzhia\b",
            r"\bcrimea\b", r"\bkherson\b", r"\bodesa\b",
        ],
        "gdelt": '(Ukraine OR Kyiv OR Zelensky OR Donbas OR Crimea)',
    },
    "nato_russia": {
        "label": "NATO / Russia",
        "patterns": [
            r"\bnato\b", r"\barticle 5\b", r"\bbaltic\b", r"\bkaliningrad\b",
            r"\bestonia\b", r"\blatvia\b", r"\blithuania\b", r"\bsuwa[lł]ki\b",
            r"\bfinland\b.*\brussia", r"\bpoland\b.*\b(drone|airspace|russia)",
            r"\bairspace violation\b",
        ],
        "gdelt": '(NATO Russia OR "Article 5" OR Kaliningrad OR "Baltic Sea" OR "airspace violation")',
    },
    "china_taiwan": {
        "label": "China / Taiwan / SCS",
        "patterns": [
            r"\btaiwan(ese)?\b", r"\btaipei\b", r"\bpla\b", r"\bsouth china sea\b",
            r"\btaiwan strait\b", r"\bscarborough\b", r"\bsecond thomas\b",
            r"\bchina\b.*\b(military|navy|warship|drills?|blockade)\b",
        ],
        "gdelt": '(Taiwan OR "South China Sea" OR "Taiwan Strait" OR PLA)',
    },
    "korea": {
        "label": "Korean Peninsula",
        "patterns": [
            r"\bnorth korea(n)?\b", r"\bpyongyang\b", r"\bkim jong[- ]un\b", r"\bdprk\b",
        ],
        "gdelt": '("North Korea" OR Pyongyang OR "Kim Jong Un")',
    },
    "india_pakistan": {
        "label": "India / Pakistan",
        "patterns": [
            r"\bindia\b.*\bpakistan\b", r"\bpakistan\b.*\bindia\b", r"\bkashmir\b",
            r"\bline of control\b",
        ],
        "gdelt": '(Kashmir OR "India Pakistan" OR "Line of Control")',
    },
}

# Only keep articles with some military / security signal. Applied to GDELT
# queries and used to filter RSS items.
CONFLICT_GDELT = '(military OR strike OR missile OR attack OR war OR troops OR drone OR nuclear OR sanctions OR ceasefire)'

# --- RSS sources (no API keys) -------------------------------------------
RSS_FEEDS = {
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Guardian World": "https://www.theguardian.com/world/rss",
    "NYT World": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "DW": "https://rss.dw.com/rdf/rss-en-world",
    "France 24": "https://www.france24.com/en/rss",
    "Kyiv Independent": "https://kyivindependent.com/news-archive/rss/",
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
}

# --- Severity rules --------------------------------------------------------
# Highest matching tier wins. 5 = civilisation-scale escalation, 1 = background.
SEVERITY_RULES = {
    5: [
        r"\bnuclear (strike|attack|detonation|explosion|weapon used)\b",
        r"\b(detonat|test)\w* (a )?nuclear (bomb|device|weapon)\b",
        r"\bdeclar\w* (of )?war\b", r"\barticle 5 (invoked|triggered)\b",
        r"\binvok\w* article 5\b", r"\bgeneral mobili[sz]ation\b",
        r"\bmartial law\b.*\bnational\b", r"\binvasion of (taiwan|poland|the baltics?)\b",
        r"\b(nato|us|american) (forces|troops|base) (attacked|struck|hit)\b",
    ],
    4: [
        r"\bballistic missiles?\b", r"\bhypersonic\b", r"\bmass(ive)? (missile|drone) (attack|strike|barrage)\b",
        r"\bmissile barrage\b", r"\bmobili[sz]ation\b", r"\bblockade\b",
        r"\bclos\w* (the )?strait\b", r"\bnuclear (plant|facility|site)\b.*\b(struck|hit|attack|strike)",
        r"\b(strike|attack)s? on (an? )?nuclear\b", r"\bkilled .*\b(commander|general|leader)\b",
        r"\bassassinat\w*\b", r"\b(launch|begin|start)\w* (an? |the )?invasion\b", r"\bground (offensive|invasion)\b",
        r"\bdirect (attack|strike|confrontation)\b", r"\bwar(ship)? sunk\b|\bsinks?\b.*\b(warship|destroyer|frigate|carrier)\b",
        r"\bairspace\b.*\b(shot down|downed)\b", r"\bevacuat\w* (embassy|citizens)\b",
    ],
    3: [
        r"\bair ?strikes?\b", r"\bmissile (strike|attack)s?\b", r"\bdrone (strike|attack)s?\b",
        r"\bshelling\b", r"\bbombard\w*\b", r"\boffensive\b", r"\bclash(es|ed)?\b",
        r"\bkilled\b", r"\bcasualties\b", r"\bdead\b", r"\bshot down\b", r"\bintercept\w*\b",
        r"\bstruck\b", r"\bexplosions?\b", r"\braids?\b", r"\bcounter-?attack\b",
        r"\bsabotage\b", r"\bseiz\w* (tanker|ship|vessel)\b",
    ],
    2: [
        r"\bdrills?\b", r"\bexercises?\b", r"\bdeploy\w*\b", r"\btroops?\b", r"\bwarships?\b",
        r"\bthreat\w*\b", r"\bwarn\w*\b", r"\bsanctions?\b", r"\bnuclear\b", r"\benrich\w*\b",
        r"\bairspace\b", r"\bincursion\b", r"\bmissile test\b", r"\blaunch\w*\b",
        r"\bescalat\w*\b", r"\bultimatum\b", r"\bretaliat\w*\b",
    ],
    1: [
        r"\btalks\b", r"\bceasefire\b", r"\btruce\b", r"\bnegotiat\w*\b", r"\bdiplomac\w*\b",
        r"\bpeace\b", r"\bsummit\b", r"\bprisoner (swap|exchange)\b", r"\baid\b",
    ],
}

# Items whose headline matches these are dropped (sport, culture, lifestyle).
OFF_TOPIC = [
    r"\b(hockey|football|soccer|olympic\w*|fifa|uefa|tennis|basketball|eurovision|box office|recipe)\b",
]

# Casualty counts bump severity: (minimum killed, floor severity)
CASUALTY_FLOORS = [(500, 5), (50, 4), (5, 3)]

# Weight of a single event in the daily "heat" index, by severity.
SEVERITY_WEIGHT = {1: 0.5, 2: 1.0, 3: 2.0, 4: 5.0, 5: 15.0}

SEVERITY_LABEL = {
    1: "Background", 2: "Posturing", 3: "Kinetic", 4: "Major escalation", 5: "Critical",
}

# --- GDELT event files -------------------------------------------------------
# Theater membership for coded events. Location codes are FIPS 10-4 (GDELT's
# ActionGeo_CountryCode); actor codes are CAMEO 3-letter country codes.
#   geo:            event happens in one of these countries
#   geo_with_actor: event happens in these countries AND involves one of these actors
#   pairs:          one actor from each set, anywhere in the world
_GULF = {"USA", "SAU", "ARE", "BHR", "QAT", "KWT", "OMN"}
_NATO = {"USA", "GBR", "FRA", "DEU", "POL", "EST", "LVA", "LTU", "FIN", "SWE", "NOR", "DNK",
         "ROU", "BGR", "CZE", "SVK", "HUN", "NLD", "BEL", "ITA", "ESP", "TUR", "CAN"}
THEATER_RULES = {
    "iran_israel": {
        "geo": {"IR", "IS", "LE", "GZ", "WE", "YM"},
        "pairs": [({"IRN"}, {"ISR"} | _GULF), ({"ISR"}, {"LBN", "SYR", "YEM", "PSE"})],
    },
    "russia_ukraine": {
        "geo": {"UP"},
        "geo_with_actor": [({"RS", "BO"}, {"UKR"})],
        "pairs": [({"RUS"}, {"UKR"})],
    },
    "nato_russia": {
        "geo_with_actor": [({"EN", "LG", "LH", "PL", "FI", "RO", "MD", "SW", "NO"}, {"RUS"})],
        "pairs": [({"RUS", "BLR"}, _NATO)],
    },
    "china_taiwan": {
        "geo": {"TW"},
        "geo_with_actor": [({"RP", "CH"}, {"TWN", "PHL"})],
        "pairs": [({"CHN"}, {"TWN", "PHL", "USA", "JPN"})],
    },
    "korea": {
        "geo": {"KN"},
        "geo_with_actor": [({"KS", "JA"}, {"PRK"})],
        "pairs": [({"PRK"}, {"KOR", "USA", "JPN"})],
    },
    "india_pakistan": {
        "pairs": [({"IND"}, {"PAK"})],
    },
}

# Severity tiers for coded events (from CAMEO codes, see gdelt_events.tier_for).
EVENT_TIER_LABEL = {
    1: "Verbal conflict", 2: "Threats & coercion", 3: "Armed violence",
    4: "Heavy weapons", 5: "Mass violence / WMD",
}
# Heat contribution per event (multiplied by 1 + log2(articles covering it)).
EVENT_TIER_WEIGHT = {1: 0.1, 2: 0.3, 3: 1.0, 4: 3.0, 5: 8.0}
