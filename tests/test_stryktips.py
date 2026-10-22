import tempfile
import unittest
from pathlib import Path

from stryktips import backtest, kupong, model, svenskaspel as ss

TEAMS = [("AIK", "Hammarby"), ("Arsenal", "Chelsea"), ("Leeds", "Burnley")]


def fake_draw(nr=4980):
    events = []
    for i in range(13):
        home, away = TEAMS[i % 3]
        events.append({
            "eventNumber": i + 1,
            "match": {"participants": [{"type": "home", "name": home}, {"type": "away", "name": away}]},
            "odds": {"one": "1,80", "x": "3,60", "two": "4,50"},
            "startOdds": {"one": "1,85", "x": "3,50", "two": "4,40"},
            # Svenska folket överspelar ettan kraftigt.
            "svenskaFolket": {"one": "70", "x": "18", "two": "12"},
            "tioTidningarsTips": {"one": 8, "x": 1, "two": 1},
        })
    return {"drawNumber": nr, "regCloseTime": "2026-10-24T15:59:00+02:00", "drawEvents": events}


def fake_result(outcomes):
    return {
        "events": [{"eventNumber": i + 1, "outcome": o} for i, o in enumerate(outcomes)],
        "distribution": [
            {"name": "13 rätt", "winners": 3, "amount": "250000,00"},
            {"name": "12 rätt", "winners": 80, "amount": "1200,00"},
            {"name": "11 rätt", "winners": 900, "amount": "90,00"},
            {"name": "10 rätt", "winners": 6000, "amount": "15,00"},
        ],
    }


class ParseTest(unittest.TestCase):
    def test_parse_draw(self):
        d = ss.parse_draw(fake_draw())
        self.assertEqual(len(d.matches), 13)
        m = d.matches[0]
        self.assertEqual(m.name, "AIK - Hammarby")
        self.assertAlmostEqual(m.odds["1"], 1.8)
        self.assertAlmostEqual(m.streck["1"], 0.70)

    def test_result_and_payouts(self):
        d = ss.parse_draw(fake_draw())
        ss.apply_result(d, fake_result(["1"] * 13))
        self.assertTrue(all(m.outcome == "1" for m in d.matches))
        self.assertEqual(d.payouts[13], 250000.0)
        self.assertEqual(d.payouts[10], 15.0)


class ModelTest(unittest.TestCase):
    def test_margin_removed(self):
        p = model.odds_to_probs({"1": 1.8, "X": 3.6, "2": 4.5})
        self.assertAlmostEqual(sum(p.values()), 1.0)
        self.assertGreater(p["1"], p["X"])

    def test_overstreckad_etta_has_low_value(self):
        m = ss.parse_draw(fake_draw()).matches[0]
        probs, source = model.match_probs(m)
        self.assertEqual(source, "odds")
        v = model.value(probs, model.match_streck(m))
        self.assertLess(v["1"], 1)
        self.assertGreater(v["2"], 1)


class SystemTest(unittest.TestCase):
    def test_budget_respected(self):
        d = ss.parse_draw(fake_draw())
        for budget in (1, 16, 64, 96, 192, 1000):
            s = kupong.build_system(d, budget=budget)
            self.assertLessEqual(s.rows, budget)
            rows = 1
            for p in s.picks:
                rows *= len(p.cover)
            self.assertEqual(rows, s.rows)

    def test_more_risk_picks_more_underdogs(self):
        d = ss.parse_draw(fake_draw())
        safe = kupong.build_system(d, budget=64, risk=0.0)
        wild = kupong.build_system(d, budget=64, risk=1.0)
        count = lambda s: sum("2" in p.cover for p in s.picks)
        self.assertGreaterEqual(count(wild), count(safe))
        self.assertGreater(safe.hit_chance, wild.hit_chance)

    def test_correct_counts(self):
        d = ss.parse_draw(fake_draw())
        ss.apply_result(d, fake_result(["1"] * 13))
        s = kupong.build_system(d, budget=1, risk=0.0)
        counts = s.correct_counts()
        self.assertEqual(sum(counts), 1)
        self.assertEqual(counts[13], 1)


class BacktestTest(unittest.TestCase):
    def test_backtest_on_saved_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = ss.RAW_DIR
            ss.RAW_DIR = Path(tmp)
            try:
                ss.save_raw("draw", 4980, fake_draw(4980))
                ss.save_raw("result", 4980, fake_result(["1"] * 13))
                ss.save_raw("draw", 4981, fake_draw(4981))  # öppen, utan resultat
                r = backtest.run(budget=1, risk=0.0)
            finally:
                ss.RAW_DIR = old
        self.assertEqual(r.draws, 1)
        self.assertEqual(r.cost, 1)
        self.assertEqual(r.payout, 250000.0)


if __name__ == "__main__":
    unittest.main()
