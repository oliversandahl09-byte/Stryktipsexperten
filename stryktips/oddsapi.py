"""Skarpare odds från The Odds API (https://the-odds-api.com).

Pinnacle används i första hand eftersom de har lägst marginal och anses ha de
träffsäkraste oddsen. Saknas Pinnacle för en match används snittet av alla
europeiska spelbolag. Kräver en API-nyckel i miljövariabeln ODDS_API_KEY;
utan nyckel används Svenska Spels egna odds precis som tidigare.

Gratisnivån ger 500 anrop i månaden. Varje anrop hämtar en hel liga, så en
körning kostar bara lika många anrop som det finns ligor på kupongen.
"""

import difflib
import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import model
from .svenskaspel import _team_names, load_raw, save_raw

API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"

# (land, liga) från Svenska Spel -> sportnyckel hos The Odds API
LEAGUES = {
    ("england", "premier league"): "soccer_epl",
    ("england", "championship"): "soccer_efl_champ",
    ("england", "league one"): "soccer_england_league1",
    ("england", "league two"): "soccer_england_league2",
    ("england", "fa cup"): "soccer_fa_cup",
    ("england", "efl cup"): "soccer_england_efl_cup",
    ("england", "league cup"): "soccer_england_efl_cup",
    ("sverige", "allsvenskan"): "soccer_sweden_allsvenskan",
    ("sweden", "allsvenskan"): "soccer_sweden_allsvenskan",
    ("sverige", "superettan"): "soccer_sweden_superettan",
    ("sweden", "superettan"): "soccer_sweden_superettan",
    ("tyskland", "bundesliga"): "soccer_germany_bundesliga",
    ("germany", "bundesliga"): "soccer_germany_bundesliga",
    ("tyskland", "2. bundesliga"): "soccer_germany_bundesliga2",
    ("germany", "2. bundesliga"): "soccer_germany_bundesliga2",
    ("spanien", "la liga"): "soccer_spain_la_liga",
    ("spain", "la liga"): "soccer_spain_la_liga",
    ("italien", "serie a"): "soccer_italy_serie_a",
    ("italy", "serie a"): "soccer_italy_serie_a",
    ("frankrike", "ligue 1"): "soccer_france_ligue_one",
    ("france", "ligue 1"): "soccer_france_ligue_one",
    ("nederländerna", "eredivisie"): "soccer_netherlands_eredivisie",
    ("netherlands", "eredivisie"): "soccer_netherlands_eredivisie",
    ("norge", "eliteserien"): "soccer_norway_eliteserien",
    ("norway", "eliteserien"): "soccer_norway_eliteserien",
    ("danmark", "superligaen"): "soccer_denmark_superliga",
    ("denmark", "superligaen"): "soccer_denmark_superliga",
    ("skottland", "premiership"): "soccer_spl",
    ("scotland", "premiership"): "soccer_spl",
}
# Ligor som heter likadant oavsett land
LEAGUES_BY_NAME = {
    "champions league": "soccer_uefa_champs_league",
    "europa league": "soccer_uefa_europa_league",
    "conference league": "soccer_uefa_europa_conference_league",
}

STOPWORDS = {"fc", "afc", "cf", "if", "ff", "bk", "sk", "fk", "ik", "the", "and", "de", "club"}


def sport_key(raw_event):
    league = (raw_event.get("match") or {}).get("league") or {}
    name = str(league.get("name", "")).strip().lower()
    country = str((league.get("country") or {}).get("name", "")).strip().lower()
    return LEAGUES.get((country, name)) or LEAGUES_BY_NAME.get(name)


def normalize_team(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("utd", "united").replace("&", " ")
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in STOPWORDS]
    return " ".join(tokens)


def team_similarity(a, b):
    a, b = normalize_team(a), normalize_team(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # "West Bromwich" mot "West Bromwich Albion", "Wolverhampton" mot "Wolverhampton Wanderers"
    if b.startswith(a) or a.startswith(b):
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def find_event(home, away, kickoff, events, threshold=0.6):
    """Hittar samma match bland The Odds APIs matcher."""
    best, best_score = None, 0.0
    for ev in events:
        start = _parse_time(ev.get("commence_time"))
        if kickoff and start and abs((start - kickoff).total_seconds()) > 12 * 3600:
            continue
        h = team_similarity(home, ev.get("home_team", ""))
        a = team_similarity(away, ev.get("away_team", ""))
        if min(h, a) < threshold:
            continue
        if h + a > best_score:
            best, best_score = ev, h + a
    return best


def _bookmaker_probs(bookmaker, home_team, away_team):
    for market in bookmaker.get("markets", []):
        if market.get("key") != "h2h":
            continue
        prices = {o.get("name"): o.get("price") for o in market.get("outcomes", [])}
        odds = {"1": prices.get(home_team), "X": prices.get("Draw"), "2": prices.get(away_team)}
        if all(isinstance(v, (int, float)) for v in odds.values()):
            return model.odds_to_probs(odds)
    return None


def event_probs(event):
    """Returnerar (sannolikheter, källa, antal spelbolag) för en match."""
    home, away = event.get("home_team"), event.get("away_team")
    per_bookmaker = {}
    for bm in event.get("bookmakers", []):
        probs = _bookmaker_probs(bm, home, away)
        if probs:
            per_bookmaker[bm.get("key")] = probs
    if not per_bookmaker:
        return None
    if "pinnacle" in per_bookmaker:
        return per_bookmaker["pinnacle"], "pinnacle", len(per_bookmaker)
    avg = {k: sum(p[k] for p in per_bookmaker.values()) / len(per_bookmaker) for k in ("1", "X", "2")}
    return model.normalize(avg), "marknadsodds", len(per_bookmaker)


def fetch_sport(sport, api_key):
    query = urllib.parse.urlencode({
        "apiKey": api_key, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal",
    })
    req = urllib.request.Request(API_URL.format(sport=sport) + "?" + query,
                                 headers={"User-Agent": "stryktipsexperten/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        remaining = resp.headers.get("x-requests-remaining")
        return json.load(resp), remaining


def match_draw(raw_draw, events_by_sport):
    """Kopplar kupongens matcher till oddsen. Returnerar {matchnummer: info}."""
    found = {}
    for ev in raw_draw.get("drawEvents", []):
        sport = sport_key(ev)
        if sport not in events_by_sport:
            continue
        home, away = _team_names(ev)
        kickoff = _parse_time((ev.get("match") or {}).get("matchStart"))
        hit = find_event(home, away, kickoff, events_by_sport[sport])
        if not hit:
            continue
        result = event_probs(hit)
        if not result:
            continue
        probs, source, n = result
        found[str(ev.get("eventNumber"))] = {
            "sannolikhet": probs,
            "kalla": source,
            "spelbolag": n,
            "match": f"{hit.get('home_team')} - {hit.get('away_team')}",
        }
    return found


def update_draw(raw_draw, api_key=None):
    """Hämtar marknadsodds för en omgång och sparar dem som data/raw/marknad_<nr>.json.

    Matcher som inte hittas den här gången (t.ex. redan startade) behåller
    oddsen från förra hämtningen.
    """
    api_key = api_key or os.environ.get("ODDS_API_KEY")
    if not api_key:
        return None
    nr = raw_draw["drawNumber"]
    sports = sorted({s for s in (sport_key(ev) for ev in raw_draw.get("drawEvents", [])) if s})
    events_by_sport, remaining = {}, None
    for sport in sports:
        try:
            events_by_sport[sport], remaining = fetch_sport(sport, api_key)
        except Exception as e:
            print(f"The Odds API: kunde inte hämta {sport}: {e}")
    previous = (load_raw("marknad", nr) or {}).get("matcher", {})
    matched = match_draw(raw_draw, events_by_sport)
    payload = {
        "hamtad": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matcher": {**previous, **matched},
    }
    save_raw("marknad", nr, payload)
    total = len(raw_draw.get("drawEvents", []))
    print(f"The Odds API: {len(matched)}/{total} matcher hittade för omgång {nr}"
          + (f", {remaining} anrop kvar denna månad" if remaining else ""))
    return payload
