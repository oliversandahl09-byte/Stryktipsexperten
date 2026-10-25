"""Aktuella serietabeller räknade från säsongens resultat hos football-data.co.uk.

Tabellen räknas fram ur alla spelade matcher i säsongens fil: tre poäng för
vinst, en för oavgjort, sorterat på poäng, målskillnad och gjorda mål.
football-data uppdaterar sina filer ett par gånger i veckan, så de senaste
matcherna kan saknas en kort tid.
"""

import json
from datetime import datetime, timezone

from .inbordes import BASE, _get, parse_csv, season_codes
from .rapport import OUT_DIR
from .svenskaspel import SPEL

# Europatipset har oftast matcher från de stora ligorna på kontinenten.
LEAGUES = {
    "stryktipset": {"E0": "Premier League", "E1": "Championship", "E2": "League One"},
    "europatipset": {"SP1": "La Liga", "I1": "Serie A", "D1": "Bundesliga", "F1": "Ligue 1"},
}.get(SPEL, {})


def standings(games):
    """Serietabell ur en lista med matcher (som parse_csv ger)."""
    table = {}
    for g in games:
        hg, ag = g["mal"]
        for team, own, other in ((g["hemma"], hg, ag), (g["borta"], ag, hg)):
            row = table.setdefault(team, {"lag": team, "s": 0, "v": 0, "o": 0, "f": 0, "gm": 0, "im": 0, "p": 0})
            row["s"] += 1
            row["gm"] += own
            row["im"] += other
            if own > other:
                row["v"] += 1
                row["p"] += 3
            elif own == other:
                row["o"] += 1
                row["p"] += 1
            else:
                row["f"] += 1
    rows = sorted(table.values(), key=lambda r: (-r["p"], -(r["gm"] - r["im"]), -r["gm"], r["lag"]))
    for i, r in enumerate(rows, 1):
        r["plac"] = i
    return rows


def build(today=None, get=_get):
    season = season_codes(today, 1)[0]
    out = {}
    for code, name in LEAGUES.items():
        try:
            games = parse_csv(get(f"{BASE}/mmz4281/{season}/{code}.csv"), code)
        except Exception as e:
            print(f"Tabell: kunde inte hämta {name}: {e}")
            continue
        out[code] = {
            "namn": name,
            "senaste_match": max((g["datum"] for g in games), default=None),
            "tabell": standings(games),
        }
    return out


def write(today=None, get=_get):
    leagues = build(today, get)
    path = OUT_DIR / "tabeller.json"
    # En serie som inte gick att hämta behåller förra tabellen.
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8")).get("serier", {})
        leagues = {**previous, **leagues}
    payload = {
        "hamtad": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kalla": "football-data.co.uk",
        "serier": leagues,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    for code, league in leagues.items():
        print(f"Tabell: {league['namn']}, {len(league['tabell'])} lag, senaste match {league.get('senaste_match')}")
    return path
