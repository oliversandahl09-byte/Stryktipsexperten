"""Skriver veckans förslag som Markdown (läsbart direkt på GitHub) och JSON."""

import json
from pathlib import Path

from .svenskaspel import OUTCOMES, SPEL, SPEL_NAMN

OUT_DIR = Path(__file__).resolve().parent.parent / "forslag"
if SPEL != "stryktipset":
    OUT_DIR = OUT_DIR / SPEL


def _pct(x):
    return f"{round(x * 100)}%"


def _cover_label(cover):
    return "".join(cover)


def to_markdown(draw, system, risk):
    lines = [
        f"# {SPEL_NAMN} omgång {draw.number}",
        "",
        f"Spelstopp: {draw.close_time or 'okänt'}  ",
        f"System: **{system.rows} rader** ({system.rows} kr), risknivå {risk}  ",
        f"Chans till 13 rätt enligt modellen: **{system.hit_chance * 100:.2f}%**",
        "",
        "| # | Match | Tips | Sannolikhet 1/X/2 | Streck 1/X/2 | Värde 1/X/2 | Källa |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in system.picks:
        m = p.match
        probs = " / ".join(_pct(p.probs[o]) for o in OUTCOMES)
        streck = " / ".join(_pct(p.streck[o]) for o in OUTCOMES) if m.streck else "–"
        value = " / ".join(
            (f"**{p.value[o]:.2f}**" if p.value[o] >= 1.15 else f"{p.value[o]:.2f}") for o in OUTCOMES
        )
        lines.append(f"| {m.number} | {m.name} | **{_cover_label(p.cover)}** | {probs} | {streck} | {value} | {p.source} |")
    lines += [
        "",
        "**Värde** = sannolikhet delat med streck. Över 1 betyder att tecknet är understreckat, "
        "alltså troligare än vad svenska folket tror. Fetstil från 1,15.",
        "",
        "Spela ansvarsfullt. Modellen ger spelvärde, inte garanterade vinster.",
    ]
    return "\n".join(lines) + "\n"


def to_dict(draw, system, risk):
    return {
        "omgang": draw.number,
        "spelstopp": draw.close_time,
        "rader": system.rows,
        "risk": risk,
        "chans13": system.hit_chance,
        "matcher": [
            {
                "nr": p.match.number,
                "match": p.match.name,
                "tips": _cover_label(p.cover),
                "sannolikhet": p.probs,
                "streck": p.streck if p.match.streck else None,
                "varde": p.value,
                "kalla": p.source,
            }
            for p in system.picks
        ],
    }


def write(draw, system, risk):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = to_markdown(draw, system, risk)
    (OUT_DIR / f"omgang_{draw.number}.md").write_text(md, encoding="utf-8")
    (OUT_DIR / "SENASTE.md").write_text(md, encoding="utf-8")
    (OUT_DIR / "senaste.json").write_text(
        json.dumps(to_dict(draw, system, risk), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return OUT_DIR / "SENASTE.md"
