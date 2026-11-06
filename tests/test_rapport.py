import tempfile
import unittest
from pathlib import Path
from unittest import mock

from stryktips import rapport, svenskaspel as ss


class PreviousPayoutTest(unittest.TestCase):
    def test_latest_result_before_draw(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ss, "RAW_DIR", Path(tmp)):
            for n in (10, 11, 12):
                ss.save_raw("draw", n, {"drawNumber": n})
            ss.save_raw("result", 10, {"events": [], "distribution": [{"name": "13 rätt", "winners": 1, "amount": "5,00"}]})
            ss.save_raw("result", 11, {
                "events": [{"eventNumber": 2, "outcome": "x"}, {"eventNumber": 1, "outcome": "1"}],
                "distribution": [{"name": "13 rätt", "winners": 63, "amount": "539682,00"},
                                 {"name": "10 rätt", "winners": 0, "amount": "0,00"}],
            })
            forra = rapport.previous_payout(12)
            self.assertEqual(forra["omgang"], 11)
            self.assertEqual(forra["rad"], "1X")
            self.assertEqual(forra["utdelning"]["13"], {"kr": 539682.0, "vinnare": 63})
            self.assertEqual(rapport.previous_payout(11)["omgang"], 10)
            self.assertIsNone(rapport.previous_payout(10))


if __name__ == "__main__":
    unittest.main()
