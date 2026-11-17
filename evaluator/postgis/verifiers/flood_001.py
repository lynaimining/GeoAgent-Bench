"""Verifier for flood_001: active schools within 500m of the Main River.

Ground truth (hidden/ground_truth.json, key flood_001_schools_within_500m_main_river_intersects)
is [1, 6, 7, 19] — computed with ST_DWithin, so the boundary case (school 7, exactly 500.000m
from the river) is INCLUDED. Schools 12 and 17 are 'closed' in schools_current and must be
excluded even if they happen to be spatially close, per the "active schools" wording.

We never read the agent's SQL to grade — only the resulting `flood_risk_schools` table and
the sandbox's own schools_current data are queried.
"""

TABLE = "flood_risk_schools"
CLOSED_SCHOOL_IDS = {12, 17}


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    expected_ids = set(ground_truth["flood_001_schools_within_500m_main_river_intersects"])

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.10, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    required_cols = {"school_id", "name", "geom"}
    cols = _columns(sandbox, TABLE)
    schema_ok = required_cols.issubset(cols)
    checks.append(("schema_has_required_columns", 0.10, schema_ok))

    ids = _school_ids(sandbox, TABLE)
    id_set_ok = ids == expected_ids
    checks.append(("correct_feature_id_set", 0.40, id_set_ok))

    if not id_set_ok:
        if 7 in expected_ids and 7 not in ids and ids != set():
            labels.append("missed_boundary_school")
        if ids & CLOSED_SCHOOL_IDS:
            labels.append("included_closed_school")
        if not ids:
            labels.append("wrong_layer")

    dup_count, invalid_count = _dupes_and_invalid(sandbox, TABLE)
    clean_ok = dup_count == 0 and invalid_count == 0
    checks.append(("no_duplicate_or_invalid_geoms", 0.15, clean_ok))
    if dup_count > 0:
        labels.append("duplicate_rows")

    crs_ok = _crs_and_type_ok(sandbox, TABLE)
    checks.append(("crs_and_geometry_type_correct", 0.15, crs_ok))
    if not crs_ok:
        labels.append("crs_error")

    names_ok = _names_match_reference(sandbox, TABLE, ids)
    checks.append(("names_match_reference", 0.10, names_ok))

    score = sum(w for _, w, ok in checks if ok)
    return score, checks, labels


def _table_exists(sandbox, table):
    rows = _q(sandbox, "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s;", (table,))
    return bool(rows)


def _columns(sandbox, table):
    rows = _q(sandbox, "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s;", (table,))
    return {r[0] for r in rows}


def _school_ids(sandbox, table):
    rows = _q(sandbox, f'SELECT school_id FROM "{table}";')
    return {r[0] for r in rows}


def _dupes_and_invalid(sandbox, table):
    dup = _q(sandbox, f'SELECT COUNT(*) FROM (SELECT school_id FROM "{table}" GROUP BY school_id HAVING COUNT(*) > 1) d;')
    invalid = _q(sandbox, f'SELECT COUNT(*) FROM "{table}" WHERE NOT ST_IsValid(geom);')
    return dup[0][0], invalid[0][0]


def _crs_and_type_ok(sandbox, table):
    # This world's tables declare plain `geometry` columns (no typmod), so geometry_columns
    # reports srid=0 for them; detect SRID/type directly from the stored data instead.
    rows = _q(
        sandbox,
        f'SELECT DISTINCT ST_SRID(geom), GeometryType(geom) FROM "{table}" WHERE geom IS NOT NULL;',
    )
    if not rows:
        return False
    srid, geom_type = rows[0]
    return len(rows) == 1 and srid == 32643 and geom_type.upper() == "POINT"


def _names_match_reference(sandbox, table, ids):
    if not ids:
        return False
    rows = _q(sandbox, f'SELECT school_id, name FROM "{table}";')
    agent_names = {r[0]: r[1] for r in rows}
    ref_rows = _q(sandbox, "SELECT school_id, name FROM schools_current WHERE school_id = ANY(%s);", (list(ids),))
    ref_names = {r[0]: r[1] for r in ref_rows}
    return agent_names == ref_names


def _q(sandbox, sql, params=None):
    import psycopg2

    conn = psycopg2.connect(sandbox.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description is not None else []
    finally:
        conn.close()
