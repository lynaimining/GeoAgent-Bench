"""Verifier for route_006: active schools farther than 2km from EVERY hospital.

The trap is the universal quantifier ("every hospital") vs. an easy-to-write but
wrong existential version (farther than 2km from *some* hospital, i.e. NOT ALL
hospitals are within 2km) — the reference uses NOT EXISTS to get this right.
"""

TABLE = "remote_schools"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    ref_rows = _q(
        sandbox,
        "SELECT s.school_id FROM schools_current s WHERE s.status='active' "
        "AND NOT EXISTS (SELECT 1 FROM hospitals h WHERE ST_DWithin(s.geom, h.geom, 2000));",
    )
    expected_ids = {r[0] for r in ref_rows}

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.15, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    schema_ok = {"school_id", "name"}.issubset(_columns(sandbox, TABLE))
    checks.append(("schema_has_required_columns", 0.15, schema_ok))

    rows = _q(sandbox, f'SELECT school_id FROM "{TABLE}";')
    ids = [r[0] for r in rows]
    id_set_ok = set(ids) == expected_ids
    checks.append(("correct_feature_id_set", 0.50, id_set_ok))
    if not id_set_ok:
        labels.append("wrong_quantifier")

    dup_ok = len(ids) == len(set(ids))
    checks.append(("no_duplicate_rows", 0.20, dup_ok))
    if not dup_ok:
        labels.append("duplicate_rows")

    score = sum(w for _, w, ok in checks if ok)
    return score, checks, labels


def _table_exists(sandbox, table):
    rows = _q(sandbox, "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s;", (table,))
    return bool(rows)


def _columns(sandbox, table):
    rows = _q(sandbox, "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s;", (table,))
    return {r[0] for r in rows}


def _q(sandbox, sql, params=None):
    import psycopg2

    conn = psycopg2.connect(sandbox.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description is not None else []
    finally:
        conn.close()
