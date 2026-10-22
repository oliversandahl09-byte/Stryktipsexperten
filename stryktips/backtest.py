"""Testar modellen på gamla omgångar: vad hade systemet kostat och gett?"""

from dataclasses import dataclass

from . import kupong
from .svenskaspel import load_draw, saved_draw_numbers


@dataclass
class BacktestResult:
    risk: float
    budget: int
    draws: int = 0
    cost: float = 0.0
    payout: float = 0.0
    best_counts: dict = None

    @property
    def roi(self):
        return (self.payout - self.cost) / self.cost if self.cost else 0.0


def playable(draw):
    return (
        draw is not None
        and len(draw.matches) == 13
        and all(m.outcome for m in draw.matches)
        and draw.payouts
    )


def run(budget=64, risk=0.5, draw_numbers=None):
    result = BacktestResult(risk=risk, budget=budget, best_counts={})
    for nr in draw_numbers or saved_draw_numbers():
        draw = load_draw(nr)
        if not playable(draw):
            continue
        system = kupong.build_system(draw, budget=budget, risk=risk)
        counts = system.correct_counts()
        result.draws += 1
        result.cost += system.rows
        result.payout += sum(counts[k] * draw.payouts.get(k, 0.0) for k in range(len(counts)))
        best = max(k for k, c in enumerate(counts) if c)
        result.best_counts[best] = result.best_counts.get(best, 0) + 1
    return result


def describe(r):
    best = ", ".join(f"{k} rätt: {r.best_counts[k]}" for k in sorted(r.best_counts, reverse=True))
    return (
        f"risk {r.risk:.1f} | {r.draws} omgångar | insats {r.cost:.0f} kr | "
        f"utdelning {r.payout:.0f} kr | avkastning {r.roi * 100:+.1f}% | bästa rad: {best or '–'}"
    )
