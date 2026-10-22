"""Inbördes möten mellan kupongens lag, från football-data.co.uk.

football-data.co.uk har gratis CSV-filer med alla resultat i de flesta
europeiska ligor, säsong för säsong. Inbördes möten letas upp i landets
divisioner de senaste tio säsongerna, så att även möten när lagen låg i en
annan division kommer med. Kräver ingen nyckel.

Resultatet sparas i forslag/inbordes.json och visas på webbsidan, där man
själv väljer hur mycket de inbördes mötena ska påverka sannolikheterna.
"""

import csv
import io
import json
import time
import urllib.request
from datetime import date, datetime

from .oddsapi import normalize_team, team_similarity
from .rapport import OUT_DIR
from .svenskaspel import _team_names

BASE = "https://www.football-data.co.uk"
SEASONS = 10
MAX_MEETINGS = 10

# Land på kupongen -> filer hos football-data. Länder med en sammanslagen fil
# för alla säsonger ("new/...") står som en sträng.
COUNTRIES = {
    "england": ["E0", "E1", "E2", "E3", "EC"],
    "skottland": ["SC0", "SC1", "SC2", "SC3"],
    "tyskland": ["D1", "D2"],
    "italien": ["I1", "I2"],
    "spanien": ["SP1", "SP2"],
    "frankrike": ["F1", "F2"],
    "nederländerna": ["N1"],
    "belgien": ["B1"],
    "portugal": ["P1"],
    "turkiet": ["T1"],
    "grekland": ["G1"],
    "sverige": "SWE",
    "norge": "NOR",
    "danmark": "DNK",
    "finland": "FIN",
    "irland": "IRL",
    "schweiz": "SWZ",
    "usa": "USA",
    "brasilien": "BRA",
}

# Svenska Spels lagnamn (normaliserade) -> football-datas, där de skiljer sig för mycket.
ALIASES = {
    "manchester city": "Man City",
    "manchester united": "Man United",
    "wolverhampton": "Wolves",
    "west bromwich": "West Brom",
    "queens park rangers": "QPR",
    "sheffield u": "Sheffield United",
    "sheffield w": "Sheffield Weds",
    "nottingham": "Nott'm Forest",
    "peterborough": "Peterboro",
    "wimbledon": "AFC Wimbledon",
    "bristol rovers": "Bristol Rvs",
    "newport": "Newport County",
    "milton keynes dons": "Milton Keynes Dons",
    "dundee u": "Dundee United",
    "dundee": "Dundee",
    "st mirren": "St Mirren",
    "bayern munchen": "Bayern Munich",
    "bayer leverkusen": "Leverkusen",
    "koln": "FC Koln",
    "paris saint germain": "Paris SG",
    "saint etienne": "St Etienne",
    "athletic bilbao": "Ath Bilbao",
    "atletico madrid": "Ath Madrid",
    "real betis": "Betis",
    "real sociedad": "Sociedad",
    "celta vigo": "Celta",
    "rayo vallecano": "Vallecano",
    "espanyol": "Espanol",
    "real oviedo": "Oviedo",
    "club brugge": "Club Brugge",
    "st truidense": "St Truiden",
    "standard liege": "Standard",
    "royale union sg": "St. Gilloise",
    "sporting lissabon": "Sp Lisbon",
    "vitoria guimaraes": "Guimaraes",
    "fc kopenhamn": "FC Copenhagen",
    "bodo glimt": "Bodo/Glimt",
    "ifk goteborg": "Goteborg",
    "ifk norrkoping": "Norrkoping",
}


def season_codes(today=None, n=SEASONS):
    """Säsongskoder som '2627' för de senaste n säsongerna, nyaste först."""
    today = today or date.today()
    start = today.year if today.month >= 7 else today.year - 1
    return [f"{(y) % 100:02d}{(y + 1) % 100:02d}" for y in range(start, start - n, -1)]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "stryktipsexperten/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8-sig", errors="replace")


def _parse_date(value):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None


def parse_csv(text, division=None):
    """Läser en football-data-fil (båda formaten) till en lista med matcher."""
    games = []
    for row in csv.DictReader(io.StringIO(text)):
        home = (row.get("HomeTeam") or row.get("Home") or "").strip()
        away = (row.get("AwayTeam") or row.get("Away") or "").strip()
        hg = row.get("FTHG") if row.get("FTHG") not in (None, "") else row.get("HG")
        ag = row.get("FTAG") if row.get("FTAG") not in (None, "") else row.get("AG")
        day = _parse_date(row.get("Date") or "")
        try:
            hg, ag = int(float(hg)), int(float(ag))
        except (TypeError, ValueError):
            continue
        if home and away and day:
            games.append({"datum": day.isoformat(), "hemma": home, "borta": away,
                          "mal": [hg, ag], "serie": division or row.get("League") or row.get("Div")})
    return games


def fetch_country(country, today=None):
    files = COUNTRIES.get(country)
    if not files:
        return []
    games = []
    if isinstance(files, str):
        try:
            games = parse_csv(_get(f"{BASE}/new/{files}.csv"))
        except Exception as e:
            print(f"Inbördes: kunde inte hämta {files}: {e}")
        oldest = f"{int(season_codes(today)[-1][:2]) + 2000}-07-01"
        return [g for g in games if g["datum"] >= oldest]
    for season in season_codes(today):
        for div in files:
            try:
                games += parse_csv(_get(f"{BASE}/mmz4281/{season}/{div}.csv"), div)
            except Exception:
                pass  # alla divisioner finns inte alla år
            time.sleep(0.2)
    return games


def resolve_team(name, known):
    """Hittar lagets namn hos football-data. Returnerar None om inget passar."""
    alias = ALIASES.get(normalize_team(name))
    if alias and alias in known:
        return alias
    best, score = None, 0.0
    for k in known:
        s = team_similarity(name, k)
        if s > score:
            best, score = k, s
    return best if score >= 0.8 else None


def head_to_head(home, away, games, limit=MAX_MEETINGS):
    """Inbördes möten, nyast först, med utfall sett från kupongens hemmalag."""
    meetings = []
    for g in games:
        if {g["hemma"], g["borta"]} != {home, away}:
            continue
        hg, ag = g["mal"]
        own, other = (hg, ag) if g["hemma"] == home else (ag, hg)
        utfall = "1" if own > other else "2" if own < other else "X"
        meetings.append({**g, "utfall": utfall, "samma_plan": g["hemma"] == home})
    meetings.sort(key=lambda m: m["datum"], reverse=True)
    # Samma match kan finnas i två filer om en division bytt kod.
    unique, seen = [], set()
    for m in meetings:
        key = (m["datum"], m["hemma"])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    unique = unique[:limit]
    summary = {o: sum(m["utfall"] == o for m in unique) for o in ("1", "X", "2")}
    return {"moten": unique, "summering": summary}


def build(raw_draw, fetch=fetch_country):
    cache, out = {}, {}
    for ev in raw_draw.get("drawEvents", []):
        league = (ev.get("match") or {}).get("league") or {}
        country = str((league.get("country") or {}).get("name", "")).strip().lower()
        if country not in cache:
            cache[country] = fetch(country)
        games = cache[country]
        if not games:
            continue
        known = {g["hemma"] for g in games} | {g["borta"] for g in games}
        home, away = _team_names(ev)
        h, a = resolve_team(home, known), resolve_team(away, known)
        if not (h and a):
            print(f"Inbördes: hittade inte {home} - {away}")
            continue
        out[str(ev.get("eventNumber"))] = {"lag": [h, a], **head_to_head(h, a, games)}
    return out


def write(raw_draw, fetch=fetch_country):
    matches = build(raw_draw, fetch)
    payload = {"omgang": raw_draw["drawNumber"], "kalla": "football-data.co.uk", "matcher": matches}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "inbordes.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    total = len(raw_draw.get("drawEvents", []))
    print(f"Inbördes: {len(matches)}/{total} matcher med inbördes möten för omgång {raw_draw['drawNumber']}")
    return path
