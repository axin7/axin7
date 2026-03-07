from __future__ import annotations

import importlib.util
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_github_heatmap.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "github_contributions_response.json"


def load_target_module():
    if not SCRIPT_PATH.exists():
        return types.SimpleNamespace()

    spec = importlib.util.spec_from_file_location("generate_github_heatmap", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GenerateGithubHeatmapTests(unittest.TestCase):
    def test_normalize_days_flattens_calendar(self) -> None:
        module = load_target_module()
        loader = getattr(module, "load_calendar_from_fixture", None)
        normalize = getattr(module, "normalize_days", None)

        self.assertIsNotNone(loader, "需要实现 load_calendar_from_fixture")
        self.assertIsNotNone(normalize, "需要实现 normalize_days")

        calendar = loader(FIXTURE_PATH)
        days = normalize(calendar)

        self.assertEqual(len(days), 14)
        self.assertEqual(days[0]["date"], "2026-01-01")
        self.assertEqual(days[0]["count"], 3)
        self.assertEqual(days[0]["row"], 3)
        self.assertEqual(days[-1]["date"], "2026-01-14")

    def test_normalize_days_maps_github_weekday_to_zero_based_rows(self) -> None:
        module = load_target_module()
        normalize = getattr(module, "normalize_days", None)

        self.assertIsNotNone(normalize, "需要实现 normalize_days")

        calendar = {
            "weeks": [
                {
                    "firstDay": "2026-01-05",
                    "contributionDays": [
                        {
                            "date": "2026-01-05",
                            "contributionCount": 1,
                            "contributionLevel": "FIRST_QUARTILE",
                            "weekday": 1,
                        },
                        {
                            "date": "2026-01-11",
                            "contributionCount": 2,
                            "contributionLevel": "SECOND_QUARTILE",
                            "weekday": 7,
                        },
                    ],
                }
            ]
        }

        days = normalize(calendar)
        self.assertEqual(days[0]["weekday"], 0)
        self.assertEqual(days[1]["weekday"], 6)

    def test_render_heatmap_svg_outputs_expected_structure(self) -> None:
        module = load_target_module()
        loader = getattr(module, "load_calendar_from_fixture", None)
        normalize = getattr(module, "normalize_days", None)
        render = getattr(module, "render_heatmap_svg", None)

        self.assertIsNotNone(loader, "需要实现 load_calendar_from_fixture")
        self.assertIsNotNone(normalize, "需要实现 normalize_days")
        self.assertIsNotNone(render, "需要实现 render_heatmap_svg")

        calendar = loader(FIXTURE_PATH)
        days = normalize(calendar)
        svg = render(days, username="axin7")

        self.assertIn("<svg", svg)
        self.assertGreaterEqual(svg.count("<rect"), 14)
        self.assertIn("GitHub Contributions", svg)
        self.assertIn('fill="#', svg)

    def test_main_generates_svg_from_fixture(self) -> None:
        module = load_target_module()
        main = getattr(module, "main", None)

        self.assertIsNotNone(main, "需要实现 main")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "heatmap.svg"
            exit_code = main(
                [
                    "--from-fixture",
                    str(FIXTURE_PATH),
                    "--output",
                    str(output_path),
                    "--username",
                    "axin7",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())
            self.assertTrue(output_path.read_text(encoding="utf-8").startswith("<svg"))


if __name__ == "__main__":
    unittest.main()
