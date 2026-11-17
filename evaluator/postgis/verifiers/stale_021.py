"""Verifier for stale_021: cross-era join between schools_2019_archive and
schools_current. All 20 schools are present in both tables (id set is trivial),
so the real trap is whether STATUS and GEOM come from the current table.

id 12 is 'active' in the archive but 'closed' in schools_current -- a status
column sourced from the archive resurrects a closed school as active.
ids 3 and 9 have different coordinates in the archive (moved since 2019) -- a
geom column sourced from the archive silently reports the wrong location.
enrollment_2019/enrollment_now happen to be numerically identical in this world's
data for every school (so delta is always 0), but the columns must still be
sourced from the correct table structurally.
"""

TABLE = "enrollment_change"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    current = {
        r[0]: {"name": r[1], "status": r[2], "enrollment": r[3]}
        for r in _q(sandbox, "SELECT school_id, name, status, enrollment FROM schools_current;")
    }
    archive_enrollment = dict(_q(sandbox, "SELECT school_id, enrollment_2019 FROM schools_2019_archive;"))
    current_geom = dict(_q(sandbox, "SELECT school_id, ST_AsText(geom) FROM schools_current;"))
    expected_ids = set(current) & set(archive_enrollment)  # all 20 in this world

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.10, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    rows = _q(
        sandbox,
        f'SELECT school_id, status, enrollment_2019, enrollment_now, delta, ST_AsText(geom) FROM "{TABLE}";',
    )
    by_id = {r[0]: r for r in rows}

    id_set_ok = set(by_id) == expected_ids
    checks.append(("correct_school_id_set", 0.15, id_set_ok))

    status_ok = all(
        by_id[i][1] == current[i]["status"] for i in expected_ids if i in by_id
    )
    checks.append(("status_reflects_current_not_archive", 0.30, status_ok))
    if not status_ok:
        labels.append("used_stale_archive")

    geom_ok = all(
        by_id[i][5] == current_geom[i] for i in (3, 9) if i in by_id
    )
    checks.append(("moved_schools_use_current_geometry", 0.30, geom_ok))
    if not geom_ok:
        labels.append("used_stale_archive")

    enrollment_ok = all(
        by_id[i][2] == archive_enrollment[i] and by_id[i][3] == current[i]["enrollment"]
        for i in expected_ids
        if i in by_id
    )
    delta_ok = all(by_id[i][4] == current[i]["enrollment"] - archive_enrollment[i] for i in expected_ids if i in by_id)
    checks.append(("enrollment_and_delta_correct", 0.15, enrollment_ok and delta_ok))
    if not (enrollment_ok and delta_ok):
        labels.append("wrong_delta")

    score = sum(w for _, w, ok in checks if ok)
    return score, checks, labels


def _table_exists(sandbox, table):
    rows = _q(sandbox, "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s;", (table,))
    return bool(rows)


def _q(sandbox, sql, params=None):
    import psycopg2

    conn = psycopg2.connect(sandbox.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description is not None else []
    finally:
        conn.close()
