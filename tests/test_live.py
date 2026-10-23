import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stryktips import live


def event(nr, status, start="2026-10-24T16:00:00+02:00", current=None, cancelled=False):
    match = {"matchStart": start, "sportEventStatus": status, "status": status.lower(), "result": []}
    if current:
        match["result"] = [{"sportEventResultType": "Current", "home": str(current[0]), "away": str(current[1])}]
    return {"eventNumber": nr, "cancelled": cancelled, "match": match}


class StateTest(unittest.TestCase):
    def test_states_and_outcome(self):
        self.assertEqual(live.match_state(event(1, "NotStarted"))["lage"], "ej startad")
        s = live.match_state(event(2, "SecondHalf", current=(2, 1)))
        self.assertEqual((s["lage"], s["mal"], s["utfall"]), ("pågår", [2, 1], "1"))
        s = live.match_state(event(3, "Ended", current=(0, 0)))
        self.assertEqual((s["lage"], s["utfall"]), ("slut", "X"))
        self.assertEqual(live.match_state(event(4, "Postponed"))["lage"], "inställd")
        self.assertNotIn("utfall", live.match_state(event(5, "NotStarted", current=(0, 0))))


class WindowTest(unittest.TestCase):
    def test_window(self):
        raw = {"drawEvents": [event(1, "NotStarted")]}
        at = lambda h, m: datetime(2026, 10, 24, h, m, tzinfo=timezone.utc)  # avspark 14:00 UTC
        self.assertFalse(live.in_live_window(raw, at(13, 30)))
        self.assertTrue(live.in_live_window(raw, at(13, 50)))
        self.assertTrue(live.in_live_window(raw, at(16, 50)))
        self.assertFalse(live.in_live_window(raw, at(17, 10)))


class WriteTest(unittest.TestCase):
    def test_writes_only_in_window(self):
        old = {"drawNumber": 1, "drawEvents": [event(1, "Ended", start="2020-01-01T16:00:00+00:00")]}
        now = datetime.now(timezone.utc).isoformat()
        current = {"drawNumber": 2, "drawEvents": [event(1, "FirstHalf", start=now, current=(0, 1))]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.json"
            self.assertIsNone(live.write(path, draws=[old]))
            self.assertFalse(path.exists())
            self.assertEqual(live.write(path, draws=[old, current]), 2)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["omgang"], 2)
        self.assertEqual(data["matcher"]["1"]["utfall"], "2")


if __name__ == "__main__":
    unittest.main()
