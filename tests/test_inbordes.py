import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from stryktips import inbordes

MAIN_CSV = """Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR
E1,21/10/2025,19:45,Wolves,West Brom,2,0,H
E1,03/02/2026,19:45,West Brom,Wolves,1,1,D
E1,04/02/2026,19:45,QPR,Swansea,0,1,A
E1,05/02/2026,19:45,Stoke,Swansea,,,
"""

NEW_CSV = """Country,League,Season,Date,Time,Home,Away,HG,AG,Res
Sweden,Allsvenskan,2024,12/05/2024,15:00,Malmo FF,AIK,3,1,H
Sweden,Allsvenskan,2010,12/05/2010,15:00,Malmo FF,AIK,0,2,A
"""


def ss_event(nr, home, away, country="England"):
    return {
        "eventNumber": nr,
        "match": {
            "league": {"name": "x", "country": {"name": country}},
            "participants": [{"type": "home", "name": home}, {"type": "away", "name": away}],
        },
    }


class SeasonTest(unittest.TestCase):
    def test_season_codes(self):
        self.assertEqual(inbordes.season_codes(date(2026, 10, 22), 3), ["2627", "2526", "2425"])
        self.assertEqual(inbordes.season_codes(date(2026, 3, 1), 2), ["2526", "2425"])


class ParseTest(unittest.TestCase):
    def test_main_format_skips_unplayed(self):
        games = inbordes.parse_csv(MAIN_CSV, "E1")
        self.assertEqual(len(games), 3)
        self.assertEqual(games[0], {"datum": "2025-10-21", "hemma": "Wolves", "borta": "West Brom",
                                    "mal": [2, 0], "serie": "E1"})

    def test_new_format(self):
        games = inbordes.parse_csv(NEW_CSV)
        self.assertEqual(games[0]["hemma"], "Malmo FF")
        self.assertEqual(games[0]["mal"], [3, 1])


class HeadToHeadTest(unittest.TestCase):
    def test_outcome_from_coupon_home_team(self):
        games = inbordes.parse_csv(MAIN_CSV, "E1")
        h2h = inbordes.head_to_head("West Brom", "Wolves", games)
        self.assertEqual([m["utfall"] for m in h2h["moten"]], ["X", "2"])
        self.assertEqual(h2h["summering"], {"1": 0, "X": 1, "2": 1})
        self.assertTrue(h2h["moten"][0]["samma_plan"])
        self.assertFalse(h2h["moten"][1]["samma_plan"])

    def test_duplicates_counted_once(self):
        games = inbordes.parse_csv(MAIN_CSV, "E1") * 2
        self.assertEqual(len(inbordes.head_to_head("Wolves", "West Brom", games)["moten"]), 2)


class ResolveTest(unittest.TestCase):
    def test_alias_and_fuzzy(self):
        known = {"Wolves", "West Brom", "QPR", "Swansea", "Bristol City"}
        self.assertEqual(inbordes.resolve_team("Wolverhampton", known), "Wolves")
        self.assertEqual(inbordes.resolve_team("Queens Park Rangers", known), "QPR")
        self.assertEqual(inbordes.resolve_team("Swansea", known), "Swansea")
        self.assertIsNone(inbordes.resolve_team("Arsenal", known))


class BuildTest(unittest.TestCase):
    def test_build_and_write(self):
        def fake_fetch(country):
            return inbordes.parse_csv(MAIN_CSV, "E1") if country == "england" else []

        raw = {"drawNumber": 4976, "drawEvents": [
            ss_event(1, "Wolverhampton", "West Bromwich"),
            ss_event(2, "Queens Park Rangers", "Swansea"),
            ss_event(3, "Arsenal", "Chelsea"),
            ss_event(4, "Malmö", "AIK", country="Sverige"),
        ]}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(inbordes, "OUT_DIR", Path(tmp)):
            path = inbordes.write(raw, fetch=fake_fetch)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["omgang"], 4976)
        self.assertEqual(sorted(data["matcher"]), ["1", "2"])
        self.assertEqual(data["matcher"]["1"]["summering"], {"1": 1, "X": 1, "2": 0})
        self.assertEqual(data["matcher"]["2"]["summering"], {"1": 0, "X": 0, "2": 1})

    def test_new_format_country_limited_to_recent_seasons(self):
        with mock.patch.object(inbordes, "_get", return_value=NEW_CSV):
            games = inbordes.fetch_country("sverige", today=date(2026, 10, 22))
        self.assertEqual([g["datum"] for g in games], ["2024-05-12"])


if __name__ == "__main__":
    unittest.main()
