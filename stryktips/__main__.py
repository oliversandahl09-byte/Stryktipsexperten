"""Kommandon:

  python -m stryktips hamta                 hämta öppna omgångar och senaste resultat
  python -m stryktips historik 4700 4980    hämta gamla omgångar (med resultat)
  python -m stryktips forslag --rader 96    skriv förslag för nästa omgång
  python -m stryktips backtest --rader 64   testa modellen på sparad historik
  python -m stryktips inbordes              inbördes möten för nästa omgång
  python -m stryktips tabell                tabeller för Premier League och Championship
"""

import argparse
import os
import sys
import time

from . import backtest, inbordes, kupong, oddsapi, rapport, svenskaspel as ss, tabell


def cmd_hamta(args):
    draws = ss.fetch_open_draws()
    for raw in draws:
        nr = raw["drawNumber"]
        ss.save_raw("draw", nr, raw)
        print(f"Sparade öppen omgång {nr}")
        if os.environ.get("ODDS_API_KEY"):
            oddsapi.update_draw(raw)
        else:
            print("Ingen ODDS_API_KEY, använder Svenska Spels odds")
    # Hämta resultat för sparade omgångar som saknar det (t.ex. förra veckan).
    open_numbers = {int(d["drawNumber"]) for d in draws}
    for nr in ss.saved_draw_numbers()[-args.bakat:]:
        if nr in open_numbers or ss.load_raw("result", nr):
            continue
        try:
            ss.save_raw("result", nr, ss.fetch_result(nr))
            print(f"Sparade resultat för omgång {nr}")
        except Exception as e:
            print(f"Inget resultat än för omgång {nr}: {e}")


def cmd_historik(args):
    for nr in range(args.fran, args.till + 1):
        if ss.load_raw("draw", nr) and ss.load_raw("result", nr) and not args.om:
            continue
        try:
            ss.save_raw("draw", nr, ss.fetch_draw(nr))
            ss.save_raw("result", nr, ss.fetch_result(nr))
            print(f"Omgång {nr} sparad")
        except Exception as e:
            print(f"Omgång {nr} misslyckades: {e}")
        time.sleep(args.paus)


def cmd_forslag(args):
    numbers = ss.saved_draw_numbers()
    candidates = [n for n in numbers if not ss.load_raw("result", n)]
    if args.omgang:
        nr = args.omgang
    elif candidates:
        nr = candidates[-1]
    else:
        sys.exit("Ingen öppen omgång sparad. Kör 'hamta' först.")
    draw = ss.load_draw(nr)
    system = kupong.build_system(draw, budget=args.rader, risk=args.risk)
    path = rapport.write(draw, system, args.risk)
    print(rapport.to_markdown(draw, system, args.risk))
    print(f"Skrev {path}")


def cmd_inbordes(args):
    candidates = [n for n in ss.saved_draw_numbers() if not ss.load_raw("result", n)]
    nr = args.omgang or (candidates[-1] if candidates else None)
    if not nr:
        sys.exit("Ingen öppen omgång sparad. Kör 'hamta' först.")
    print(f"Skrev {inbordes.write(ss.load_raw('draw', nr))}")


def cmd_tabell(args):
    print(f"Skrev {tabell.write()}")


def cmd_backtest(args):
    risks = [i / 10 for i in range(0, 11, 2)] if args.svep else [args.risk]
    for risk in risks:
        print(backtest.describe(backtest.run(budget=args.rader, risk=risk)))


def main(argv=None):
    p = argparse.ArgumentParser(prog="stryktips", description="Stryktipsexperten")
    sub = p.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("hamta", help="hämta öppna omgångar och nya resultat")
    h.add_argument("--bakat", type=int, default=5, help="hur många sparade omgångar bakåt som kollas för resultat")
    h.set_defaults(func=cmd_hamta)

    hi = sub.add_parser("historik", help="hämta gamla omgångar")
    hi.add_argument("fran", type=int)
    hi.add_argument("till", type=int)
    hi.add_argument("--paus", type=float, default=1.0, help="sekunder mellan anrop")
    hi.add_argument("--om", action="store_true", help="hämta om även redan sparade")
    hi.set_defaults(func=cmd_historik)

    for name, func in (("forslag", cmd_forslag), ("backtest", cmd_backtest)):
        sp = sub.add_parser(name)
        sp.add_argument("--rader", type=int, default=64, help="max antal rader (1 kr/rad)")
        sp.add_argument("--risk", type=float, default=0.5, help="0 = säkra tecken, 1 = jaga skrällar")
        sp.set_defaults(func=func)
        if name == "forslag":
            sp.add_argument("--omgang", type=int)
        else:
            sp.add_argument("--svep", action="store_true", help="testa flera risknivåer")

    ib = sub.add_parser("inbordes", help="inbördes möten för nästa omgång")
    ib.add_argument("--omgang", type=int)
    ib.set_defaults(func=cmd_inbordes)

    sub.add_parser("tabell", help="tabeller för Premier League och Championship").set_defaults(func=cmd_tabell)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
