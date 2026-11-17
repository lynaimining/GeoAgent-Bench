"""Invoke an explicitly configured adapter and store controller receipts."""

import os
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

from .common import read_json, write_json
from .protocol import inspect_run, numeric_checks


def run_adapter(task, rubric, work, command, timeout):
    if not command:
        raise ValueError("Provide an adapter command after --adapter")
    work = Path(work).resolve()
    contract = read_json(work / "TASK_CONTRACT.json")
    if contract["id"] != task["id"]:
        raise ValueError("Staged task ID does not match requested task")
    if list((work / "outputs").iterdir()):
        raise ValueError("Use a freshly staged run with empty outputs")
    receipts = work.with_name(work.name + ".controller")
    receipts.mkdir(exist_ok=False)
    setup = task.get("postgis")
    context = nullcontext()
    if setup:
        from .postgis import evaluate, world

        context = world(setup)
    started = time.monotonic()
    status, returncode = "unknown", None
    try:
        with context as database:
            env = dict(os.environ)
            env.pop("BENCH_DB_DSN", None)
            env.update(
                BENCH_TASK_ID=task["id"], BENCH_INPUT_DIR=str(work / "inputs"),
                BENCH_OUTPUT_DIR=str(work / "outputs"), BENCH_PROMPT=str(work / "TASK_PROMPT.md"),
                BENCH_TASK_CONTRACT=str(work / "TASK_CONTRACT.json"), PYTHONIOENCODING="utf-8",
            )
            if database:
                env["BENCH_DB_DSN"] = database.agent_dsn
            with (receipts / "stdout.log").open("wb") as stdout, (receipts / "stderr.log").open("wb") as stderr:
                try:
                    proc = subprocess.run(
                        command, cwd=work, env=env, stdout=stdout, stderr=stderr, timeout=timeout,
                        check=False, shell=False,
                    )
                    returncode = proc.returncode
                    status = "adapter_exited" if returncode == 0 else "adapter_failed"
                except subprocess.TimeoutExpired:
                    status = "adapter_timeout"
            report = inspect_run(task, work)
            write_json(receipts / "artifacts.json", report)
            if status == "adapter_exited" and report["status"] == "ready_for_review":
                values = numeric_checks(task, work, rubric)
                if values is not None:
                    write_json(receipts / "numeric.json", values)
                if setup:
                    result = read_json(work / "outputs/result.json")
                    write_json(receipts / "postgis.json", evaluate(setup, database, result))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        status = "controller_error"
        write_json(receipts / "error.json", {"error": str(error)})
        raise
    finally:
        write_json(receipts / "receipt.json", {
            "task_id": task["id"], "status": status, "adapter_returncode": returncode,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": timeout, "score": None,
        })
    return status, receipts
