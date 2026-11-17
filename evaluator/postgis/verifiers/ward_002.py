"""Verifier for ward_002: schools per ward, using the hidden ground truth's
precomputed ward->school_id assignment (spatial containment, any status)."""

TABLE = "schools_per_ward"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    expected_counts = {int(w): len(ids) for w, ids in ground_truth["schools_per_ward"].items()}

    exists = _table_exists(sandbox, TABLE)
    checks.append(("output_table_exists", 0.10, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    required = {"ward_id", "ward_name", "population", "school_count"}
    schema_ok = required.issubset(_columns(sandbox, TABLE))
    checks.append(("schema_has_required_columns", 0.10, schema_ok))

    rows = _q(sandbox, f'SELECT ward_id, school_count FROM "{TABLE}";')
    actual_counts = {r[0]: r[1] for r in rows}
    counts_ok = actual_counts == expected_counts
    checks.append(("school_counts_match_ground_truth", 0.40, counts_ok))
    if not counts_ok:
        labels.append("wrong_join_predicate")

    ordered_rows = _q(sandbox, f'SELECT ward_id FROM "{TABLE}";')
    ward_ids_in_order = [r[0] for r in ordered_rows]
    ordering_ok = ward_ids_in_order == sorted(ward_ids_in_order)
    checks.append(("ordered_by_ward_id_ascending", 0.15, ordering_ok))
    if not ordering_ok:
        labels.append("wrong_ordering")

    pop_rows = _q(sandbox, f'SELECT ward_id, population FROM "{TABLE}";')
    ref_pop_rows = _q(sandbox, "SELECT ward_id, population FROM wards;")
    pop_ok = dict(pop_rows) == dict(ref_pop_rows)
    checks.append(("population_matches_source", 0.15, pop_ok))
    if not pop_ok:
        labels.append("population_mismatch")

    all_wards_present = set(actual_counts) == set(expected_counts)
    checks.append(("all_six_wards_present", 0.10, all_wards_present))

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
