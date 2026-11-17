"""Verifier for repair_025: school_locations_broken has correct attributes for
every active school, but geometries for schools 3 and 9 were sourced from the
stale 2019 archive (they moved since then). Attribute columns give no hint
anything is wrong -- only a spatial check (ST_Equals against schools_current)
catches it.
"""

TABLE = "school_locations_broken"
TOLERANCE_M = 0.01


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    current = {
        r[0]: {"name": r[1], "status": r[2], "enrollment": r[3], "geom": r[4]}
        for r in _q(sandbox, "SELECT school_id, name, status, enrollment, ST_AsText(geom) FROM schools_current WHERE status='active';")
    }

    exists = _table_exists(sandbox, TABLE)
    checks.append(("table_still_exists", 0.15, exists))
    if not exists:
        labels.append("fix_incomplete")
        return 0.0, checks, labels

    rows = _q(sandbox, f'SELECT school_id, name, status, enrollment, ST_AsText(geom) FROM "{TABLE}";')
    actual = {r[0]: {"name": r[1], "status": r[2], "enrollment": r[3], "geom": r[4]} for r in rows}

    id_set_ok = set(actual) == set(current)
    checks.append(("correct_school_set", 0.15, id_set_ok))

    attrs_ok = all(
        sid in actual
        and actual[sid]["name"] == v["name"]
        and actual[sid]["status"] == v["status"]
        and actual[sid]["enrollment"] == v["enrollment"]
        for sid, v in current.items()
    )
    checks.append(("attributes_unchanged", 0.15, attrs_ok))
    if not attrs_ok:
        labels.append("fix_incomplete")

    geom_matches = _q(
        sandbox,
        f'SELECT s.school_id FROM "{TABLE}" b JOIN schools_current s ON s.school_id = b.school_id '
        f"WHERE ST_DWithin(b.geom, s.geom, {TOLERANCE_M});",
    )
    matched_ids = {r[0] for r in geom_matches}
    geom_ok = matched_ids == set(current)
    checks.append(("geometry_matches_current_locations", 0.55, geom_ok))
    if not geom_ok:
        labels.append("used_stale_archive")

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
