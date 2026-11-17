"""Disposable PostGIS worlds and upstream final-state verifiers."""

import os
import runpy
import secrets
import subprocess
import time
from contextlib import contextmanager
from types import SimpleNamespace

from .common import ROOT, path_at, read_json

IMAGE = "postgis/postgis@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5"


def docker(*args, env=None, timeout=30):
    proc = subprocess.run(
        ["docker", *args], check=False, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=timeout,
    )
    if proc.returncode:
        raise RuntimeError(f"Docker {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def seed(dsn, setup):
    import psycopg2
    from psycopg2 import sql

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        world = setup["world_id"]
        cur.execute(path_at(ROOT, f"environments/postgis/{world}/seed.sql").read_text(encoding="utf-8"))
        if setup.get("scenario_sql"):
            cur.execute(path_at(ROOT, setup["scenario_sql"]).read_text(encoding="utf-8"))
        cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cur.execute("REVOKE TEMPORARY ON DATABASE bench FROM PUBLIC")
        cur.execute("GRANT USAGE ON SCHEMA public TO bench_agent")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO bench_agent")
        if setup["mode"] == "repair":
            table = sql.Identifier(setup["output_contract"]["table"])
            cur.execute(sql.SQL("GRANT UPDATE (geom) ON public.{} TO bench_agent").format(table))
        elif setup["mode"] != "abstain":
            cur.execute("GRANT CREATE ON SCHEMA public TO bench_agent")


def make_role(dsn, password):
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("CREATE ROLE bench_agent LOGIN PASSWORD %s CONNECTION LIMIT 8", (password,))
        cur.execute("ALTER ROLE bench_agent SET statement_timeout = '30s'")
        cur.execute("ALTER ROLE bench_agent SET idle_in_transaction_session_timeout = '30s'")


def wait_ready(dsn):
    import psycopg2

    for _ in range(45):
        try:
            with psycopg2.connect(dsn, connect_timeout=2) as conn, conn.cursor() as cur:
                cur.execute("SELECT postgis_full_version()")
                return cur.fetchone()[0]
        except psycopg2.Error:
            time.sleep(1)
    raise RuntimeError("Disposable PostGIS did not become ready")


@contextmanager
def world(setup):
    admin_pw, agent_pw = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    env = dict(os.environ, POSTGRES_PASSWORD=admin_pw, POSTGRES_DB="bench")
    container = docker(
        "run", "--detach", "--rm", "--platform", "linux/amd64",
        "--publish", "127.0.0.1::5432", "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB",
        "--label", "org.lynaimining.geoagent-bench=ephemeral", IMAGE, env=env, timeout=300,
    )
    try:
        mapping = docker("port", container, "5432/tcp")
        port = int(mapping.splitlines()[0].rsplit(":", 1)[1])
        admin = f"dbname=bench host=127.0.0.1 port={port} user=postgres password={admin_pw}"
        agent = f"dbname=bench host=127.0.0.1 port={port} user=bench_agent password={agent_pw}"
        version = wait_ready(admin)
        make_role(admin, agent_pw)
        seed(admin, setup)
        evaluator = admin + " options='-c default_transaction_read_only=on -c statement_timeout=15000'"
        yield SimpleNamespace(dsn=evaluator, agent_dsn=agent, version=version)
    finally:
        docker("rm", "-f", container)


def evaluate(setup, db, result):
    from psycopg2 import Error

    task_id = setup["task_id"]
    truth = read_json(path_at(ROOT, f"evaluator/postgis/ground_truth/{setup['world_id']}.json"))
    verify = runpy.run_path(str(path_at(ROOT, f"evaluator/postgis/verifiers/{task_id}.py")))["verify"]
    upstream_run = SimpleNamespace(
        status="blocked" if result.get("status") == "needs_clarification" else result.get("status"),
        reason_code=result.get("reason_code"),
    )
    try:
        score, checks, labels = verify(db, truth, upstream_run)
    except Error as error:
        return {"status": "verifier_query_failed", "sqlstate": error.pgcode, "source_task": task_id}
    return {
        "status": "verified_end_state", "source_task": task_id, "postgis_version": db.version,
        "weighted_score": float(score), "author_binary_pass": bool(checks) and all(ok for _, _, ok in checks),
        "checks": [{"name": label, "weight": weight, "passed": bool(ok)} for label, weight, ok in checks],
        "failure_labels": labels,
    }
