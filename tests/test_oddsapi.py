import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stryktips import model, oddsapi, svenskaspel as ss


def ss_event(nr, home, away, league="Championship"):
    return {
        "eventNumber": nr,
        "match": {
            "matchStart": "2026-10-24T16:00:00+02:00",
            "league": {"name": league, "country": {"name": "England"}},
            "participants": [{"type": "home", "name": home}, {"type": "away", "name": away}],
        },
        "odds": {"one": "2,10", "x": "3,40", "two": "3,50"},
        "svenskaFolket": {"one": "60", "x": "20", "two": "20"},
    }


def odds_event(home, away, books):
    return {
        "home_team": home,
        "away_team": away,
        "commence_time": "2026-10-24T14:00:00Z",
        "bookmakers": [
            {"key": key, "markets": [{"key": "h2h", "outcomes": [
                {"name": home, "price": o1}, {"name": "Draw", "price": ox}, {"name": away, "price": o2},
            ]}]}
            for key, (o1, ox, o2) in books.items()
        ],
    }


CHAMP = [
    odds_event("Preston North End", "West Bromwich Albion", {"pinnacle": (3.9, 3.6, 2.0), "unibet": (3.7, 3.5, 2.0)}),
    odds_event("Queens Park Rangers", "Swansea City", {"unibet": (2.4, 3.4, 3.0), "betsson": (2.5, 3.3, 2.9)}),
    odds_event("Stoke City", "Bristol City", {"pinnacle": (2.4, 3.3, 3.1)}),
]


class MatchingTest(unittest.TestCase):
    def test_team_names(self):
        self.assertGreater(oddsapi.team_similarity("West Bromwich", "West Bromwich Albion"), 0.9)
        self.assertGreater(oddsapi.team_similarity("Wolverhampton", "Wolverhampton Wanderers"), 0.9)
        self.assertGreater(oddsapi.team_similarity("Man Utd", "Manchester United"), 0.6)
        self.assertLess(oddsapi.team_similarity("Stoke", "Bristol City"), 0.6)

    def test_bristol_not_confused_with_stoke(self):
        hit = oddsapi.find_event("Stoke", "Bristol City", None, CHAMP)
        self.assertEqual(hit["home_team"], "Stoke City")

    def test_league_mapping(self):
        self.assertEqual(oddsapi.sport_key(ss_event(1, "A", "B", "Premier League")), "soccer_epl")
        self.assertEqual(oddsapi.sport_key(ss_event(1, "A", "B", "League One")), "soccer_england_league1")
        self.assertIsNone(oddsapi.sport_key(ss_event(1, "A", "B", "Okänd liga")))


class ProbsTest(unittest.TestCase):
    def test_pinnacle_preferred(self):
        probs, source, n = oddsapi.event_probs(CHAMP[0])
        self.assertEqual(source, "pinnacle")
        self.assertEqual(n, 2)
        self.assertAlmostEqual(sum(probs.values()), 1.0)
        self.assertGreater(probs["2"], probs["1"])

    def test_market_average_without_pinnacle(self):
        probs, source, n = oddsapi.event_probs(CHAMP[1])
        self.assertEqual(source, "marknadsodds")
        self.assertEqual(n, 2)
        self.assertAlmostEqual(sum(probs.values()), 1.0)


class UpdateDrawTest(unittest.TestCase):
    def test_saved_and_used_by_model(self):
        raw = {"drawNumber": 4976, "regCloseTime": None, "drawEvents": [
            ss_event(1, "Preston", "West Bromwich"),
            ss_event(2, "Queens Park Rangers", "Swansea"),
            ss_event(3, "Okänt lag", "Annat lag"),
        ]}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(ss, "RAW_DIR", Path(tmp)), \
                mock.patch.object(oddsapi, "fetch_sport", return_value=(CHAMP, "497")) as fetch:
            ss.save_raw("draw", 4976, raw)
            oddsapi.update_draw(raw, api_key="nyckel")
            draw = ss.load_draw(4976)
        fetch.assert_called_once_with("soccer_efl_champ", "nyckel")
        sources = [model.match_probs(m)[1] for m in draw.matches]
        self.assertEqual(sources, ["pinnacle", "marknadsodds", "odds"])

    def test_no_key_does_nothing(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch.object(oddsapi, "fetch_sport") as fetch:
            self.assertIsNone(oddsapi.update_draw({"drawNumber": 1, "drawEvents": []}))
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
