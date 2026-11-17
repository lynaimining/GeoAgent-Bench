"""Paths, encoding and data identity shared by the controller."""

import csv
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = re.compile(r"G200-(?:0[1-9]|1[0-3])-[SC]\d\d\Z")


def path_at(root, relative):
    """Resolve a portable path within root, rejecting symlink escapes."""
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise ValueError(f"Invalid relative path: {relative!r}")
    if any(part in ("", ".", "..") for part in relative.split("/")):
        raise ValueError(f"Invalid relative path: {relative!r}")
    path = root.joinpath(*PurePosixPath(relative).parts).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes its directory: {relative}")
    return path


def read_json(path):
    def invalid(token):
        raise ValueError(f"Non-finite JSON value in {path.name}: {token}")

    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=invalid)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def identity(path):
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def matches(path, record):
    return path.is_file() and path.stat().st_size == record["bytes"] and sha256(path) == record["sha256"]


def all_tasks():
    return jsonl(ROOT / "tasks/tasks.jsonl")


def lookup(task_id):
    task = next((task for task in all_tasks() if task["id"] == task_id), None)
    if task is None:
        raise ValueError(f"Unknown task: {task_id}")
    return task


def rubric_for(task_id):
    rubric = next(
        (item for item in jsonl(ROOT / "evaluator/rubrics.jsonl") if item["task_id"] == task_id), None
    )
    if rubric is None:
        raise ValueError(f"Unknown task: {task_id}")
    return rubric
