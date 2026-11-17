"""Verifier for pipe_012: 4-stage pipeline (spatial filter -> elevation filter ->
enrollment ranking -> schema/rowcount). Confirmed against the data: exactly 3
active schools satisfy both filters (6, 19, 7), with distinct enrollments (no
ties), so the top-5 constraint returns all 3 with ranks 1-3.

Checkpoint weights are diagnostic (visible per-stage failure localization);
binary_pass still requires every check to pass -- a pipeline that's "close" is
not graded as a partial success for ranking purposes, only for the paper's
failure-taxonomy breakdown.
"""

TABLE = "flood_risk_ranked"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    ref_rows = _q(
        sandbox,
        """
        SELECT s.school_id, s.enrollment
        FROM schools_current s
        JOIN wards w ON ST_Contains(w.geom, s.geom)
        WHERE s.status='active'
        AND EXISTS (SELECT 1 FROM rivers r WHERE ST_DWithin(s.geom, r.geom, 800))
        AND w.avg_elevation_m < 550
        ORDER BY s.enrollment DESC;
        """,
    )
    expected_order = [r[0] for r in ref_rows]
    expected_ids = set(expected_order)

    exists = _table_exists(sandbox, TABLE)
    # weight 0: a missing table already early-returns score 0.0 below, so this
    # check would otherwise double-count on top of the 4 stage weights (which
    # already sum to 1.0), pushing the max possible weighted_score to 1.15.
    checks.append(("output_table_exists", 0.0, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    rows = _q(sandbox, f'SELECT school_id, rank FROM "{TABLE}" ORDER BY rank;')
    actual_ids = {r[0] for r in rows}

    # Stage: spatial filter -- every row the agent kept must be within 800m of a river.
    river_ok_ids = {
        r[0]
        for r in _q(
            sandbox,
            "SELECT s.school_id FROM schools_current s WHERE EXISTS "
            "(SELECT 1 FROM rivers r WHERE ST_DWithin(s.geom, r.geom, 800));",
        )
    }
    spatial_ok = actual_ids.issubset(river_ok_ids)
    checks.append(("spatial_filter_stage", 0.25, spatial_ok))
    if not spatial_ok:
        labels.append("wrong_spatial_filter")

    # Stage: elevation filter -- every row the agent kept must be in a low-elevation ward.
    elev_ok_ids = {
        r[0]
        for r in _q(
            sandbox,
            "SELECT s.school_id FROM schools_current s JOIN wards w ON ST_Contains(w.geom, s.geom) "
            "WHERE w.avg_elevation_m < 550;",
        )
    }
    elevation_ok = actual_ids.issubset(elev_ok_ids)
    checks.append(("elevation_filter_stage", 0.25, elevation_ok))
    if not elevation_ok:
        labels.append("wrong_elevation_filter")

    # Stage: full set + rank order matches reference exactly.
    actual_order = [r[0] for r in rows]
    ranking_ok = actual_order == expected_order
    checks.append(("ranking_stage", 0.35, ranking_ok))
    if not ranking_ok:
        labels.append("wrong_ranking")

    schema_ok = {"school_id", "name", "enrollment", "rank"}.issubset(_columns(sandbox, TABLE))
    row_count_ok = len(rows) == len(expected_order)
    checks.append(("schema_and_rowcount", 0.15, schema_ok and row_count_ok))

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
