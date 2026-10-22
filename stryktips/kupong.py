"""Bygger ett system (spikar, halv- och helgarderingar) inom en budget.

Antalet rader blir 2^halvgarderingar * 3^helgarderingar. För varje match
väljs vilka tecken som ska täckas. Poängen för ett val väger ihop

  * träffchans:  summan av sannolikheterna för de täckta tecknen
  * spelvärde:   summan av sannolikhet/streck för de täckta tecknen

med vikten `risk` (0 = bara träffchans, 1 = bara spelvärde). Dynamisk
programmering hittar det system med högst total poäng som ryms i budgeten.
"""

import math
from dataclasses import dataclass
from itertools import combinations

from . import model
from .svenskaspel import OUTCOMES

CHOICES = [c for size in (1, 2, 3) for c in combinations(OUTCOMES, size)]


@dataclass
class MatchPick:
    match: object
    probs: dict
    streck: dict
    value: dict
    source: str
    cover: tuple

    @property
    def hit_chance(self):
        return sum(self.probs[o] for o in self.cover)


@dataclass
class System:
    picks: list
    rows: int

    @property
    def hit_chance(self):
        """Sannolikheten för 13 rätt med systemet."""
        return math.prod(p.hit_chance for p in self.picks)

    def correct_counts(self):
        """Antal rader med k rätt, givet utfallen. Returnerar lista index=k."""
        poly = [1]
        for p in self.picks:
            outcome = p.match.outcome
            if outcome is None:
                return None
            hit = 1 if outcome in p.cover else 0
            miss = len(p.cover) - hit
            new = [0] * (len(poly) + 1)
            for k, c in enumerate(poly):
                new[k] += c * miss
                new[k + 1] += c * hit
            poly = new
        return poly


def _score(probs, value, cover, risk):
    hit = sum(probs[o] for o in cover)
    val = sum(value[o] for o in cover)
    return (1 - risk) * math.log(max(hit, 1e-9)) + risk * math.log(max(val, 1e-9))


def build_system(draw, budget=64, risk=0.5):
    analysed = []
    for m in draw.matches:
        probs, source = model.match_probs(m)
        streck = model.match_streck(m)
        analysed.append((m, probs, streck, model.value(probs, streck), source))

    # dp[(halv, hel)] = (poäng, lista med valda tecken)
    dp = {(0, 0): (0.0, [])}
    for m, probs, streck, value, _ in analysed:
        nxt = {}
        for (h, f), (score, chosen) in dp.items():
            for cover in CHOICES:
                nh, nf = h + (len(cover) == 2), f + (len(cover) == 3)
                if 2 ** nh * 3 ** nf > budget:
                    continue
                s = score + _score(probs, value, cover, risk)
                if (nh, nf) not in nxt or s > nxt[(nh, nf)][0]:
                    nxt[(nh, nf)] = (s, chosen + [cover])
        dp = nxt

    (h, f), (_, covers) = max(dp.items(), key=lambda kv: kv[1][0])
    picks = [
        MatchPick(match=m, probs=probs, streck=streck, value=value, source=source, cover=cover)
        for (m, probs, streck, value, source), cover in zip(analysed, covers)
    ]
    return System(picks=picks, rows=2 ** h * 3 ** f)
