"""The checks that have to pass before CI may publish this page."""
import copy
import hashlib
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import contributions  # noqa: E402
import sheets  # noqa: E402
from printer import THEMES  # noqa: E402

PROFILE = json.loads((ROOT / "profile.json").read_text())
PORTRAIT = json.loads((ROOT / "data/portrait.json").read_text())
MEASURED = {
    "ran_at": "2026-11-04T07:37:00Z",
    "checks": {
        "careos_pgtap": {"status": "pass", "tests": 1800, "files": 44, "migrations": 59},
        "hft_tests": {"status": "pass", "tests": 153},
        "hft_falsification": {"status": "pass", "t": -5.65},
        "hft_noise": {"status": "pass"},
        "hft_power": {"status": "pass", "t": 16.7},
        "visionaid_tests": {"status": "pass", "tests": 60},
        "mslc_tests": {"status": "pass", "tests": 47},
        "evidence_links": {"status": "pass", "links": 14, "missing": []},
    },
    "rounds": [
        {"family": "dead", "date": "2026-07-07", "t": -2.9, "stability": 0.3, "result": "FAIL"},
        {"family": "buried", "date": "2026-07-07", "t": -40.0, "stability": 0.2, "result": "FAIL-family-dead"},
        {"family": "alive", "date": "2026-07-07", "t": 3.5, "stability": 1.0, "result": "PASS"},
        {"family": "unsure", "date": "2026-07-07", "t": None, "stability": None, "result": "PASS-provisional"},
    ],
}


def hero(verification):
    return sheets.hero(True, THEMES["light"], PROFILE, verification, PORTRAIT)


class Honesty(unittest.TestCase):
    def test_a_failed_check_prints_in_red(self):
        broken = copy.deepcopy(MEASURED)
        broken["checks"]["hft_power"]["status"] = "fail"
        svg = hero(broken)
        self.assertRegex(svg, r'class="t red end">FAILED<')
        self.assertIn("8 checks ran. 1 failed.", svg)
        self.assertNotIn("+16.70", svg)

    def test_a_check_that_could_not_run_loses_its_pass(self):
        partial = copy.deepcopy(MEASURED)
        partial["checks"]["careos_pgtap"]["status"] = "error"
        svg = hero(partial)
        self.assertIn(">not run<", svg)
        self.assertIn("7 checks ran. 0 failed. 1 did not run.", svg)

    def test_killed_count_comes_from_the_log(self):
        self.assertIn(">2 of 4<", hero(MEASURED))

    def test_published_readme_has_no_unmeasured_values(self):
        readme = (ROOT / "README.md").read_text()
        self.assertNotIn("{{", readme)
        self.assertNotIn("n/a", readme)
        self.assertNotIn("not run", (ROOT / "assets" / re.search(r"hero-wide-light-\w+\.svg", readme)[0]).read_text())


class LedgerSheet(unittest.TestCase):
    def test_digests_follow_the_sql_formula(self):
        rows = sheets.chain()
        first = "|".join((sheets.TENANT, "41", sheets.EVENTS[0][1], "", "system", "form.signed", "form", "", '{"form": 17}'))
        self.assertEqual(rows[0]["hash"], hashlib.sha256(b"\x00" + first.encode()).digest())
        self.assertEqual(rows[1]["prev"], rows[0]["hash"])

    def test_the_edit_changes_the_digest(self):
        rows = sheets.chain()
        index = next(i for i, row in enumerate(rows) if row["id"] == sheets.TAMPERED_ID)
        edited = sheets.event_digest(rows[index]["prev"], sheets.EVENTS[index], sheets.TAMPERED_PAYLOAD)
        self.assertNotEqual(edited, rows[index]["hash"])


class DotPlot(unittest.TestCase):
    def test_marks_zero_and_the_gate(self):
        track, gate, marks = sheets.plot_row(None, 53, -8, 18)
        self.assertEqual(track.index(":"), 16)
        self.assertEqual(gate.index("|"), 20)
        self.assertEqual(marks, "")

    def test_off_scale_values_point_left(self):
        marks = sheets.plot_row(-33.2, 53, -8, 18)[2]
        self.assertEqual(marks[0], "<")


class Calendar(unittest.TestCase):
    HTML = """
    <td data-date="2026-01-02" id="c-1" data-level="2" class="ContributionCalendar-day"></td>
    <tool-tip for="c-1">12 contributions on January 2nd.</tool-tip>
    <td data-date="2026-01-01" id="c-0" data-level="0" class="ContributionCalendar-day"></td>
    <tool-tip for="c-0">No contributions on January 1st.</tool-tip>
    <td data-date="2026-01-03" id="c-2" data-level="4" class="ContributionCalendar-day"></td>
    <tool-tip for="c-2">1,204 contributions on January 3rd.</tool-tip>
    """

    def test_parses_counts_and_sorts_days(self):
        days = contributions.parse(self.HTML)
        self.assertEqual([d["count"] for d in days], [0, 12, 1204])
        self.assertEqual(contributions.longest_streak(days), 2)


class Assets(unittest.TestCase):
    def test_every_sheet_works_inside_an_img_tag(self):
        svgs = list((ROOT / "assets").glob("*.svg"))
        self.assertTrue(svgs)
        for path in svgs:
            source = path.read_text()
            ET.fromstring(source)  # must be well formed
            self.assertLess(len(source), 120_000, path.name)
            self.assertNotIn("<script", source)
            self.assertNotRegex(source, r"url\(https?:")

    def test_readme_images_exist(self):
        readme = (ROOT / "README.md").read_text()
        names = re.findall(r"/assets/([\w-]+\.svg)", readme)
        self.assertGreaterEqual(len(names), 12)
        for name in names:
            self.assertTrue((ROOT / "assets" / name).exists(), name)

    def test_each_picture_stays_one_html_block(self):
        readme = (ROOT / "README.md").read_text()
        for block in re.findall(r"<p><a href=.*?</picture></a></p>", readme, re.S):
            self.assertNotIn("\n\n", block)
        self.assertEqual(readme.count("<picture>"), len(re.findall(r"<p><a href=[^>]+><picture>", readme)))

    def test_the_source_photo_stays_out(self):
        tracked = [p for p in ROOT.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic"} and ".git" not in p.parts]
        self.assertEqual(tracked, [])


if __name__ == "__main__":
    unittest.main()
