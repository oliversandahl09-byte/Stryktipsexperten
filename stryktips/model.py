"""Sannolikheter och spelvärde.

Grundidén: oddsen säger hur troligt varje tecken är, strecken säger hur många
andra som spelar det. Ett tecken som är troligare än strecken antyder är
understreckat och ger mer i utdelning när det går in.
"""

from .svenskaspel import OUTCOMES


def odds_to_probs(odds):
    """Gör om odds till sannolikheter och räknar bort spelbolagets marginal."""
    if not odds or any(not o or o <= 1 for o in odds.values()):
        return None
    raw = {k: 1 / v for k, v in odds.items()}
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def tio_tidningar_probs(tips):
    if not tips or sum(tips.values()) <= 0:
        return None
    # Lite utjämning så att ett tecken utan tidningar inte får sannolikhet 0.
    smoothed = {k: v + 1 for k, v in tips.items()}
    total = sum(smoothed.values())
    return {k: v / total for k, v in smoothed.items()}


def normalize(dist):
    total = sum(dist.values())
    return {k: v / total for k, v in dist.items()}


def match_probs(match):
    """Bästa uppskattningen av sannolikheten för 1, X och 2 i en match.

    Ordning: aktuella odds, startodds, Tio tidningars tips och sist strecken.
    Returnerar (sannolikheter, källa).
    """
    for source, probs in (
        ("odds", odds_to_probs(match.odds)),
        ("startodds", odds_to_probs(match.start_odds)),
        ("tio tidningar", tio_tidningar_probs(match.tio_tidningar)),
    ):
        if probs:
            return probs, source
    if match.streck:
        return normalize(match.streck), "streck"
    return {k: 1 / 3 for k in OUTCOMES}, "ingen data"


def match_streck(match):
    if match.streck and sum(match.streck.values()) > 0:
        # Golv på 1 % så att ett nollstreckat tecken inte ger oändligt värde.
        return normalize({k: max(v, 0.01) for k, v in match.streck.items()})
    return {k: 1 / 3 for k in OUTCOMES}


def value(probs, streck):
    """Spelvärde per tecken: sannolikhet / streck. Över 1 betyder understreckat."""
    return {k: probs[k] / streck[k] for k in OUTCOMES}
