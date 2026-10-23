"""Liveresultat för den öppna omgången, för webbsidan.

Svenska Spels API tillåter inte anrop direkt från en annan webbplats (CORS),
så webbsidan kan inte hämta ställningarna själv. I stället körs det här från
GitHub Actions med några minuters mellanrum medan matcherna pågår, och
resultatet publiceras som live.json bredvid sidan.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import svenskaspel as ss

ENDED = {"Ended", "EndedAfterExtratime", "EndedAfterPenalties", "Fulltime"}
NOT_STARTED = {"NotStarted"}
# Matcher räknas som aktuella från en kvart före avspark till tre timmar efter.
BEFORE, AFTER = timedelta(minutes=15), timedelta(hours=3)


def _start(event):
    value = (event.get("match") or {}).get("matchStart")
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def in_live_window(raw_draw, now=None):
    """Sant om någon match på kupongen pågår eller nyss har slutat."""
    now = now or datetime.now(timezone.utc)
    return any(start and start - BEFORE <= now <= start + AFTER
               for start in map(_start, raw_draw.get("drawEvents", [])))


def _score(match):
    results = match.get("result") or []
    for kind in ("Current", "Fulltime"):
        for r in results:
            if r.get("sportEventResultType") == kind:
                try:
                    return [int(r["home"]), int(r["away"])]
                except (KeyError, TypeError, ValueError):
                    pass
    return None


def match_state(event):
    match = event.get("match") or {}
    status = match.get("sportEventStatus") or "NotStarted"
    score = _score(match)
    if status in NOT_STARTED:
        state = "ej startad"
    elif status in ENDED:
        state = "slut"
    elif status in {"Postponed", "Cancelled"} or event.get("cancelled"):
        state = "inställd"
    elif status == "Interrupted":
        state = "avbruten"
    else:
        state = "pågår"
    out = {"lage": state, "status": match.get("status") or "", "start": match.get("matchStart")}
    if score and state != "ej startad":
        hg, ag = score
        out["mal"] = score
        out["utfall"] = "1" if hg > ag else "2" if hg < ag else "X"
    return out


def build(raw_draw):
    return {
        "omgang": raw_draw.get("drawNumber"),
        "hamtad": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "matcher": {str(ev.get("eventNumber")): match_state(ev) for ev in raw_draw.get("drawEvents", [])},
    }


def candidates():
    """Öppna omgångar och den senast sparade omgången utan resultat.

    Efter spelstopp listas omgången inte längre som öppen, så den sparade
    behövs för att följa matcherna medan de spelas.
    """
    yield from ss.fetch_open_draws()
    saved = [n for n in ss.saved_draw_numbers() if not ss.load_raw("result", n)]
    if saved:
        yield ss.fetch_draw(saved[-1])


def write(out_path, force=False, draws=None):
    """Skriver live.json för den omgång som spelas nu. Returnerar omgångsnumret,
    eller None om ingen match är aktuell (då skrivs ingenting)."""
    for raw in draws if draws is not None else candidates():
        if raw and (force or in_live_window(raw)):
            out_path = Path(out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(build(raw), ensure_ascii=False, indent=1), encoding="utf-8")
            return raw.get("drawNumber")
    return None
