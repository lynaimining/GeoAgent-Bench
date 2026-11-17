import json
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
