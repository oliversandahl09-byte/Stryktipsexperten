import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from stryktips import tabell

CSV = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR
E0,16/08/2026,Arsenal,Chelsea,2,0,H
E0,17/08/2026,Chelsea,Everton,1,1,D
E0,23/08/2026,Everton,Arsenal,0,0,D
E0,24/08/2026,Fulham,Everton,3,1,H
E0,30/08/2026,Fulham,Arsenal,,,
"""


class StandingsTest(unittest.TestCase):
    def test_points_and_order(self):
        rows = tabell.standings(tabell.parse_csv(CSV, "E0"))
        self.assertEqual([r["lag"] for r in rows], ["Arsenal", "Fulham", "Everton", "Chelsea"])
        arsenal = rows[0]
        self.assertEqual((arsenal["s"], arsenal["v"], arsenal["o"], arsenal["f"], arsenal["p"]), (2, 1, 1, 0, 4))
        self.assertEqual((arsenal["gm"], arsenal["im"], arsenal["plac"]), (2, 0, 1))
        # Fulham och Everton: 3 mot 2 poäng
        self.assertEqual(rows[1]["p"], 3)
        self.assertEqual(rows[2]["p"], 2)

    def test_goal_difference_breaks_tie(self):
        csv = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\nE1,01/09/2026,A,B,1,0,H\nE1,02/09/2026,C,D,3,0,H\n"
        self.assertEqual([r["lag"] for r in tabell.standings(tabell.parse_csv(csv))][:2], ["C", "A"])


class WriteTest(unittest.TestCase):
    def test_write_uses_current_season_and_keeps_failed_league(self):
        urls = []

        def fake_get(url):
            urls.append(url)
            if url.endswith("E1.csv"):
                raise OSError("nere")
            return CSV

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(tabell, "OUT_DIR", Path(tmp)):
            (Path(tmp) / "tabeller.json").write_text(json.dumps({"serier": {"E1": {"namn": "Championship", "tabell": []}}}))
            path = tabell.write(today=date(2026, 10, 23), get=fake_get)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(urls[0].endswith("/mmz4281/2627/E0.csv"))
        self.assertEqual(data["serier"]["E0"]["tabell"][0]["lag"], "Arsenal")
        self.assertEqual(data["serier"]["E0"]["senaste_match"], "2026-08-24")
        self.assertIn("E1", data["serier"])


if __name__ == "__main__":
    unittest.main()
