import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from geoagent_bench.common import ROOT, lookup, read_json, rubric_for
from geoagent_bench.data import Inputs
from geoagent_bench.protocol import inspect_run, prepare
from geoagent_bench.runner import run_adapter


class ProtocolTests(unittest.TestCase):
    def test_offline_submission_and_tamper_detection(self):
        task = lookup("G200-08-S04")
        rubric = rubric_for(task["id"])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = prepare(task, Inputs(root / "cache", offline=True), root / "case")
            self.assertFalse((run / "evaluator").exists())
            self.assertFalse((run / "environment").exists())
            staged = read_json(run / "TASK_CONTRACT.json")
            self.assertEqual(set(staged["inputs"]), set(task["input_paths"]))
            self.assertNotIn("criteria", staged)
            status, _ = run_adapter(
                task, rubric, run, [sys.executable, str(ROOT / "examples/interval_coverage.py")], 60,
            )
            self.assertEqual(status, "adapter_exited")
            self.assertEqual(inspect_run(task, run)["status"], "ready_for_review")
            self.assertEqual(
                read_json(run / "outputs/coverage.json")["rows"],
                read_json(ROOT / rubric["reference_path"])["rows"],
            )
            with (run / "inputs" / task["input_paths"][0]).open("ab") as stream:
                stream.write(b"changed")
            self.assertEqual(inspect_run(task, run)["status"], "invalid_submission")

    def test_license_acknowledgment_before_fetch(self):
        task = lookup("G200-06-S01")
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "CC BY-NC"):
                prepare(task, Inputs(Path(folder) / "cache", offline=True), Path(folder) / "case")


    def test_earth_prompt_uses_only_question_and_choice_fields(self):
        task = lookup("G200-06-S18")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            roster = root / "source.json"
            roster.write_text(
                '{"210": {"evaluation": [{"question": "Measure the area.", "gt_answer": "hidden"}],'
                ' "choices": [3, 4], "dialogs": ["hidden"]}, "unused": NaN}',
                encoding="utf-8",
            )
            loader = Inputs(root / "cache", offline=True, accept_nc=True)
            with patch.object(loader, "_payload", return_value=roster):
                self.assertEqual(loader.source_prompt(task), "Measure the area.\n\nA. 3\nB. 4")


if __name__ == "__main__":
    unittest.main()
