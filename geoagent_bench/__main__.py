"""Command line for listing, preparing, running and reviewing tasks."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.error import URLError

from .common import ROOT, TASK_ID, all_tasks, jsonl, lookup, matches, path_at, read_json, rubric_for
from .data import Inputs
from .protocol import inspect_run, numeric_checks, prepare
from .review import blank_review, score_review
from .runner import run_adapter


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def validate():
    tasks = all_tasks()
    suite = read_json(ROOT / "tasks/suite.json")
    manifest = read_json(ROOT / "assets/manifest.json")
    rubrics = jsonl(ROOT / "evaluator/rubrics.jsonl")
    index = {r["task_id"]: r for r in rubrics}
    ids = {t["id"] for t in tasks}
    if len(tasks) != 200 or len(ids) != 200 or len(rubrics) != 200 or set(index) != ids:
        raise ValueError("Expected 200 unique task/rubric pairs")
    if Counter(t["difficulty"] for t in tasks) != {"single": 170, "composite": 30}:
        raise ValueError("Unexpected difficulty quotas")
    if Counter(t["origin"] for t in tasks) != suite["counts"]["origin"]:
        raise ValueError("Unexpected provenance quotas")
    expected = {(d["code"], k): d[k] for d in suite["domains"] for k in ("single", "composite")}
    if Counter((t["domain"], t["difficulty"]) for t in tasks) != expected:
        raise ValueError("Unexpected domain quotas")
    files = manifest["files"]
    for relative, asset in files.items():
        path_at(ROOT / "assets/bundled", relative)
        if asset["mode"] == "bundled" and not matches(ROOT / "assets/bundled" / relative, asset):
            raise ValueError(f"Bundled asset mismatch: {relative}")
        if asset["mode"] == "derived" and relative not in manifest["assemblies"][asset["assembly"]]["outputs"]:
            raise ValueError(f"Missing derivative recipe: {relative}")
    for t in tasks:
        name = t["id"]
        rubric = index[name]
        if not TASK_ID.fullmatch(name) or name.split("-")[1] != t["domain"]:
            raise ValueError(f"Invalid task ID: {name}")
        if not t["goal"] or not t["source_records"] or not t["input_paths"] or not t["profiles"]:
            raise ValueError(f"Missing task contract: {name}")
        if len(t["stages"]) not in (range(3, 6) if t["difficulty"] == "composite" else [0]):
            raise ValueError(f"Incorrect stage count: {name}")
        if not set(t["input_paths"]) <= files.keys() or any(not k.startswith("data/") for k in t["input_paths"]):
            raise ValueError(f"Invalid task input: {name}")
        if sum(c["points"] for c in rubric["criteria"]) != 100:
            raise ValueError(f"Invalid rubric weights: {name}")
        if rubric.get("reference_path"):
            read_json(path_at(ROOT, rubric["reference_path"]))
        if t["origin"] == "public_original" and not (t.get("original_prompt") or t.get("earth_original")):
            raise ValueError(f"Missing original prompt binding: {name}")
    withheld = {
        "G200-05-S05": ("labeled_grid", "fold_grid", "oof_predictions"),
        "G200-05-S06": ("fold_grid", "oof_predictions"),
        "G200-05-C02": ("oof_predictions",),
    }
    for t in tasks:
        for forbidden in withheld.get(t["id"], []):
            if any(forbidden in path for path in t["input_paths"]):
                raise ValueError(f"Target leakage: {t['id']} / {forbidden}")
    splits = read_json(ROOT / "tasks/grouped_splits.json")["groups"]
    if Counter(x for group in splits for x in group["tasks"]) != Counter(ids):
        raise ValueError("Source-sharing groups must cover each task once")
    emit({"status": "catalog_valid", "counts": suite["counts"], "groups": len(splits),
          "bundled_files_checked": sum(a["mode"] == "bundled" for a in files.values()),
          "external_file_specs": sum(a["mode"] != "bundled" for a in files.values()),
          "agent_runs": 0})


def add_input_options(parser):
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache")
    parser.add_argument("--library", type=Path, help="Root with the author snapshots listed in the manifest")
    parser.add_argument("--geobenchx-archive", type=Path, help="Path to the author's verified Data.zip")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--accept-noncommercial", action="store_true", help="Include CC BY-NC 4.0 Earth inputs")


def inputs_for(args):
    return Inputs(args.cache, library=args.library, archive=args.geobenchx_archive,
                  offline=args.offline, accept_nc=args.accept_noncommercial)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    cli = parser.add_subparsers(dest="command", required=True)
    cli.add_parser("validate", help="Offline catalog, reference and bundled-file checks")
    ls = cli.add_parser("list", help="Browse task IDs and run profiles")
    ls.add_argument("--domain")
    ls.add_argument("--profile")
    ls.add_argument("--difficulty", choices=["single", "composite"])
    one = cli.add_parser("show", help="Show a task definition and its provenance")
    one.add_argument("task")
    fetch = cli.add_parser("fetch", help="Fetch, reconstruct and verify input files")
    selection = fetch.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task", action="append")
    selection.add_argument("--domain")
    selection.add_argument("--all", action="store_true")
    add_input_options(fetch)
    stage = cli.add_parser("prepare", help="Stage one task into a new directory")
    stage.add_argument("task")
    stage.add_argument("--dest", type=Path, required=True)
    add_input_options(stage)
    run = cli.add_parser("run", help="Run an explicit adapter against a prepared task")
    run.add_argument("task")
    run.add_argument("--work", type=Path, required=True)
    run.add_argument("--timeout", type=int, default=900)
    run.add_argument("--adapter", nargs=argparse.REMAINDER, required=True)
    check = cli.add_parser("inspect", help="Check submitted artifacts and numeric comparisons where available")
    check.add_argument("task")
    check.add_argument("--work", type=Path, required=True)
    review = cli.add_parser("review-form", help="Write a blank human review with per-task criteria")
    review.add_argument("task")
    review.add_argument("--output", type=Path, required=True)
    score = cli.add_parser("score", help="Calculate the result of an evidence-backed human review")
    score.add_argument("task")
    score.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "validate":
            validate()
        elif args.command == "list":
            tasks = [
                t for t in all_tasks()
                if (not args.domain or t["domain"] == args.domain)
                and (not args.profile or args.profile in t["profiles"])
                and (not args.difficulty or t["difficulty"] == args.difficulty)
            ]
            for t in tasks:
                nc = "  [CC BY-NC data]" if t["noncommercial_data"] else ""
                print(f"{t['id']}  {t['difficulty']:9s} {','.join(t['profiles']):12s} {t['title']}{nc}")
        elif args.command == "show":
            emit(lookup(args.task))
        elif args.command == "fetch":
            tasks = [lookup(x) for x in args.task] if args.task else [
                t for t in all_tasks() if not args.domain or t["domain"] == args.domain
            ]
            if not tasks:
                raise ValueError("No tasks matched")
            source = inputs_for(args)
            skipped, completed = [], []
            input_paths = set()
            for t in tasks:
                if t["noncommercial_data"] and not source.accept_nc and not args.task:
                    skipped.append(t["id"])
                    continue
                paths, _ = source.fetch_task(t)
                completed.append(t["id"])
                input_paths.update(paths)
            emit({"status": "inputs_verified", "tasks": len(completed), "unique_input_paths": len(input_paths),
                  "noncommercial_skipped": skipped})
        elif args.command == "prepare":
            task = lookup(args.task)
            directory = prepare(task, inputs_for(args), args.dest)
            emit({"task_id": task["id"], "work": str(directory), "status": "prepared"})
        elif args.command == "run":
            if args.timeout <= 0:
                raise ValueError("Timeout must be positive")
            task = lookup(args.task)
            status, path = run_adapter(task, rubric_for(args.task), args.work, args.adapter, args.timeout)
            emit({"task_id": args.task, "status": status, "receipts": str(path)})
            return 0 if status == "adapter_exited" else 1
        elif args.command == "inspect":
            task = lookup(args.task)
            result = inspect_run(task, args.work)
            if result["status"] == "ready_for_review":
                result["numeric_check"] = numeric_checks(task, args.work, rubric_for(args.task))
            emit(result)
            return 0 if result["status"] == "ready_for_review" else 1
        elif args.command == "review-form":
            blank_review(rubric_for(args.task), args.output)
            emit({"task_id": args.task, "status": "review_form_created", "path": str(args.output)})
        elif args.command == "score":
            emit(score_review(rubric_for(args.task), read_json(args.review)))
    except (ValueError, RuntimeError, KeyError, URLError, ImportError, OSError) as error:
        print(f"geoagent_bench: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
