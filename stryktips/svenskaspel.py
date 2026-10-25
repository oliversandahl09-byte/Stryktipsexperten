"""Hämtar och tolkar data från Svenska Spels (inofficiella) API för Stryktipset.

Rådata sparas som JSON under data/raw/ så att streck och odds finns kvar även
efter att Svenska Spel slutat visa dem för gamla omgångar.
"""

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# Vilket spel som hämtas. Europatipset har samma API och samma kupongformat,
# så allt annat fungerar likadant. Andra spel än Stryktipset sparas i egna mappar.
SPEL = os.environ.get("SPEL", "stryktipset").strip().lower() or "stryktipset"
SPEL_NAMN = {"stryktipset": "Stryktipset", "europatipset": "Europatipset"}.get(SPEL, SPEL.capitalize())
BASE_URL = f"https://api.spela.svenskaspel.se/draw/1/{SPEL}"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
if SPEL != "stryktipset":
    RAW_DIR = RAW_DIR / SPEL
OUTCOMES = ("1", "X", "2")


def _get_json(url, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": "stryktipsexperten/0.1", "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def fetch_open_draws():
    data = _get_json(f"{BASE_URL}/draws")
    return data.get("draws", [])


def fetch_draw(draw_number):
    data = _get_json(f"{BASE_URL}/draws/{draw_number}")
    return data.get("draw", data)


def fetch_result(draw_number):
    data = _get_json(f"{BASE_URL}/draws/{draw_number}/result")
    return data.get("result", data)


def save_raw(kind, draw_number, payload):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{kind}_{draw_number}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_raw(kind, draw_number):
    path = RAW_DIR / f"{kind}_{draw_number}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value):
    """Svenska Spel skickar tal som strängar med decimalkomma, t.ex. "1,70"."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _triplet(obj):
    if not isinstance(obj, dict):
        return None
    values = [to_float(obj.get(k)) for k in ("one", "x", "two")]
    if any(v is None for v in values):
        return None
    return dict(zip(OUTCOMES, values))


@dataclass
class Match:
    number: int
    home: str
    away: str
    odds: dict | None = None          # aktuella odds från Svenska Spel
    start_odds: dict | None = None
    streck: dict | None = None        # svenska folket, andel 0..1
    tio_tidningar: dict | None = None  # antal tidningar per tecken
    outcome: str | None = None        # "1", "X" eller "2" när matchen är spelad
    market: dict | None = None        # sannolikheter från The Odds API, se oddsapi.py
    market_source: str | None = None

    @property
    def name(self):
        return f"{self.home} - {self.away}"


@dataclass
class Draw:
    number: int
    close_time: str | None
    matches: list[Match] = field(default_factory=list)
    payouts: dict = field(default_factory=dict)  # antal rätt -> utdelning per rad (kr)


def _team_names(event):
    match = event.get("match") or {}
    home = away = None
    for p in match.get("participants", []):
        if p.get("type") == "home":
            home = p.get("name") or p.get("mediumName")
        elif p.get("type") == "away":
            away = p.get("name") or p.get("mediumName")
    if not (home and away) and event.get("description"):
        parts = event["description"].split("-", 1)
        if len(parts) == 2:
            home, away = home or parts[0].strip(), away or parts[1].strip()
    return home or "?", away or "?"


def parse_draw(raw):
    matches = []
    for ev in raw.get("drawEvents", []):
        home, away = _team_names(ev)
        streck = _triplet(ev.get("svenskaFolket"))
        if streck:
            streck = {k: v / 100 for k, v in streck.items()}
        matches.append(Match(
            number=int(ev.get("eventNumber", len(matches) + 1)),
            home=home,
            away=away,
            odds=_triplet(ev.get("odds")),
            start_odds=_triplet(ev.get("startOdds")),
            streck=streck,
            tio_tidningar=_triplet(ev.get("tioTidningarsTips")),
        ))
    matches.sort(key=lambda m: m.number)
    return Draw(number=int(raw["drawNumber"]), close_time=raw.get("regCloseTime"), matches=matches)


def _payout_rows(distribution):
    payouts = {}
    for item in distribution or []:
        label = str(item.get("name") or item.get("description") or "")
        m = re.search(r"(\d+)", label)
        if not m:
            continue
        payouts[int(m.group(1))] = to_float(item.get("amount")) or 0.0
    return payouts


def apply_result(draw, raw_result):
    by_number = {m.number: m for m in draw.matches}
    for ev in raw_result.get("events", []):
        m = by_number.get(int(ev.get("eventNumber", 0)))
        if m is None or ev.get("cancelled"):
            continue
        outcome = str(ev.get("outcome", "")).upper()
        if outcome in OUTCOMES:
            m.outcome = outcome
    draw.payouts = _payout_rows(raw_result.get("distribution"))
    return draw


def load_draw(draw_number):
    """Läser en omgång från lokalt sparad rådata (med resultat om det finns)."""
    raw = load_raw("draw", draw_number)
    if raw is None:
        return None
    draw = parse_draw(raw)
    result = load_raw("result", draw_number)
    if result:
        apply_result(draw, result)
    market = (load_raw("marknad", draw_number) or {}).get("matcher", {})
    for m in draw.matches:
        info = market.get(str(m.number))
        if info:
            m.market, m.market_source = info["sannolikhet"], info["kalla"]
    return draw


def saved_draw_numbers():
    if not RAW_DIR.exists():
        return []
    return sorted(int(p.stem.split("_")[1]) for p in RAW_DIR.glob("draw_*.json"))
