"""Example adapter for G200-08-S04. Compute assay coverage from staged CSVs."""

import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from shutil import copyfile


def main():
    if os.environ["BENCH_TASK_ID"] != "G200-08-S04":
        raise ValueError("This example is specific to G200-08-S04")
    source = Path(os.environ["BENCH_INPUT_DIR"]) / "data/synthetic/mining/drill2"
    output = Path(os.environ["BENCH_OUTPUT_DIR"])
    collars = source / "01_collar.csv"
    assays = source / "03_assay.csv"
    by_hole = defaultdict(list)
    with assays.open(encoding="utf-8", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            start, end = float(row["from"]), float(row["to"])
            if 0 <= start < end:
                by_hole[row["hole_id"]].append((start, end, index))

    rows = []
    with collars.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            hole, depth = row["hole_id"], float(row["max_depth"])
            merged, beyond = [], []
            for start, end, index in sorted(by_hole[hole]):
                if end > depth:
                    beyond.append(index)
                end = min(end, depth)
                if start >= end:
                    continue
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])
            gaps = []
            prev = 0.0
            for start, end in [*merged, [depth, depth]]:
                if start > prev:
                    gaps.append([prev, start])
                prev = end
            covered = sum(end-start for start, end in merged)
            rows.append({
                "hole_id": hole, "max_depth_m": depth, "covered_m": covered,
                "coverage_fraction": covered / depth, "gaps": gaps, "beyond_bottom_rows": beyond,
            })
    artifact = output / "coverage.json"
    artifact.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    reopened = json.loads(artifact.read_text(encoding="utf-8"))["rows"]
    if reopened != rows:
        raise ValueError("Coverage readback mismatch")
    copyfile(__file__, output / "interval_coverage.py")
    result = {
        "status": "completed", "summary": "Assay coverage computed from clipped interval unions.",
        "metrics": [{"name": "holes", "value": len(reopened), "unit": "holes"}],
        "artifacts": [
            {"path": "coverage.json", "readback": f"Parsed {len(reopened)} hole rows"},
            {"path": "interval_coverage.py", "readback": "Executed script copied into the result"},
        ],
        "evidence": [{
            "detail": "Used collar.max_depth and the assay from/to columns. Overlapping intervals count once.",
            "tool": "Python csv", "inputs": [f"data/synthetic/mining/drill2/{p.name}" for p in (collars, assays)],
            "parameters": {"depth_unit": "m", "report_out_of_bounds": True},
        }],
        "limitations": ["Synthetic teaching data"],
    }
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
