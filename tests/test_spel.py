import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
import json
from stryktips import rapport, svenskaspel as ss, tabell
print(json.dumps({"url": ss.BASE_URL, "raw": str(ss.RAW_DIR), "ut": str(rapport.OUT_DIR),
                  "namn": ss.SPEL_NAMN, "serier": list(tabell.LEAGUES)}))
"""


def settings(spel=None):
    env = {k: v for k, v in os.environ.items() if k != "SPEL"}
    if spel:
        env["SPEL"] = spel
    out = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


class SpelTest(unittest.TestCase):
    def test_stryktipset_is_default(self):
        s = settings()
        self.assertTrue(s["url"].endswith("/draw/1/stryktipset"))
        self.assertEqual(Path(s["raw"]), ROOT / "data" / "raw")
        self.assertEqual(Path(s["ut"]), ROOT / "forslag")
        self.assertIn("E0", s["serier"])

    def test_europatipset_has_own_folders(self):
        s = settings("europatipset")
        self.assertTrue(s["url"].endswith("/draw/1/europatipset"))
        self.assertEqual(Path(s["raw"]), ROOT / "data" / "raw" / "europatipset")
        self.assertEqual(Path(s["ut"]), ROOT / "forslag" / "europatipset")
        self.assertEqual(s["namn"], "Europatipset")
        self.assertEqual(s["serier"][:3], ["E0", "E1", "SP1"])


if __name__ == "__main__":
    unittest.main()
