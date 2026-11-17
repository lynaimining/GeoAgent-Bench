"""Verifier for stale_005: data-grounding trap.

The world has two schools tables: schools_current (authoritative) and
schools_2019_archive (stale — ground_truth['moved_since_archive'] = [3, 9] have
different coordinates in the archive, and ground_truth['stale_status_in_archive']
= [12] is wrongly 'active' in the archive when it is actually 'closed').

Even if an agent pulls the right ID set from the archive by coincidence, comparing
geometry for schools 3 and 9 against schools_current catches archive use directly.
"""

TABLE = "current_active_schools"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    expected_ids = {
        r[0] for r in _q(sandbox, "SELECT school_id FROM schools_current WHERE status='active';")
    }
    moved_ids = ground_truth["moved_since_archive"]
    ref_geom = dict(
        _q(sandbox, "SELECT school_id, ST_AsText(geom) FROM schools_current WHERE school_id = ANY(%s);", (moved_ids,))
    )

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.10, exists))
    if not exists:
        labels.append("used_stale_archive")
        return 0.0, checks, labels

    schema_ok = {"school_id", "name", "geom"}.issubset(_columns(sandbox, TABLE))
    checks.append(("schema_has_required_columns", 0.10, schema_ok))

    rows = _q(sandbox, f'SELECT school_id FROM "{TABLE}";')
    ids = [r[0] for r in rows]
    id_set_ok = set(ids) == expected_ids
    checks.append(("correct_active_id_set", 0.30, id_set_ok))
    if not id_set_ok and 12 in set(ids):
        labels.append("included_closed_school")

    geom_rows = _q(sandbox, f'SELECT school_id, ST_AsText(geom) FROM "{TABLE}" WHERE school_id = ANY(%s);', (moved_ids,))
    actual_geom = dict(geom_rows)
    geom_ok = all(actual_geom.get(i) == ref_geom.get(i) for i in moved_ids if i in expected_ids)
    checks.append(("moved_schools_use_current_coordinates", 0.30, geom_ok))
    if not geom_ok:
        labels.append("used_stale_archive")

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
