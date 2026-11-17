"""Verifier for crs_007: same flood-risk question as flood_001, but in a world
where `rivers` and `schools_current` are stored in EPSG:4326 while everything
else (and the required output) is EPSG:32643. Correct solutions must reproject
before measuring distance in metres.

Reference is computed in this module (not reused from my_world_v0's ground_truth,
since round-trip reprojection introduces sub-metre drift that flips the exact-500m
boundary case) via ST_Transform on both sides before ST_DWithin.

School 7 (the exact-500m boundary case) is a DON'T-CARE here, not scored either
way: confirmed live that its planar (ST_Transform-then-ST_DWithin) distance is
500.00000000004...m -- a razor-thin float artifact of this world's reprojection
round-trip, not geographic reality -- while its true spheroidal distance
(ST_Distance on ::geography) is 498.7m, safely inside 500m. A model using
::geography (a legitimately more accurate distance method) correctly includes
school 7 and was wrongly failed by a reference tied to one brittle convention.
Every other school's distance is nowhere near the boundary, so this is scoped
narrowly to school 7 alone.
"""

TABLE = "flood_risk_schools"
BOUNDARY_SCHOOL_ID = 7


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    ref_rows = _q(
        sandbox,
        "SELECT s.school_id FROM schools_current s, rivers r "
        "WHERE r.name = 'Main River' AND s.status = 'active' "
        "AND ST_DWithin(ST_Transform(s.geom, 32643), ST_Transform(r.geom, 32643), 500);",
    )
    expected_ids = {r[0] for r in ref_rows}
    expected_core = expected_ids - {BOUNDARY_SCHOOL_ID}

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.10, exists))
    if not exists:
        labels.append("crs_error")
        return 0.0, checks, labels

    schema_ok = {"school_id", "name", "geom"}.issubset(_columns(sandbox, TABLE))
    checks.append(("schema_has_required_columns", 0.10, schema_ok))

    ids = {r[0] for r in _q(sandbox, f'SELECT school_id FROM "{TABLE}";')}
    id_set_ok = (ids - {BOUNDARY_SCHOOL_ID}) == expected_core
    checks.append(("correct_feature_id_set", 0.40, id_set_ok))
    if not id_set_ok:
        if len(ids) > len(expected_ids) + 3:
            labels.append("used_degrees_as_metres")
        else:
            labels.append("missing_reprojection")

    crs_rows = _q(
        sandbox, f'SELECT DISTINCT ST_SRID(geom) FROM "{TABLE}" WHERE geom IS NOT NULL;'
    )
    crs_ok = len(crs_rows) == 1 and crs_rows[0][0] == 32643
    checks.append(("output_geometry_is_epsg_32643", 0.25, crs_ok))
    if not crs_ok:
        labels.append("crs_error")

    dup_ok = len(ids) == len({r[0] for r in _q(sandbox, f'SELECT school_id FROM "{TABLE}";')})
    checks.append(("no_duplicate_rows", 0.15, dup_ok))

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
