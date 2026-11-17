"""Verifier for pipe_014: nearest-hospital catchment aggregation. Every hospital
must appear even with zero assigned schools -- a plain INNER JOIN silently drops
empty catchments, which is the completeness stage this verifier catches.

School 6 sits at an EXACT tie between two hospitals (921.9544...m from both City
General and Riverside Clinic -- confirmed live: two logically-equivalent nearest-
hospital queries broke the tie differently and both are valid). Any single
"the" reference assignment is unfair to a model that legitimately tie-breaks the
other way, so this verifier enumerates every valid tie-break combination and
accepts a match against any of them, rather than requiring one arbitrary pick.
"""

import itertools

TABLE = "hospital_catchments"
TIE_EPSILON_M = 1e-6


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    all_hospitals = {r[0]: r[1] for r in _q(sandbox, "SELECT hospital_id, name FROM hospitals;")}
    per_school = _q(
        sandbox,
        "SELECT s.school_id, s.enrollment, h.hospital_id, ST_Distance(s.geom, h.geom) AS dist "
        "FROM schools_current s, hospitals h WHERE s.status = 'active';",
    )
    by_school: dict[int, dict] = {}
    for school_id, enrollment, hospital_id, dist in per_school:
        rec = by_school.setdefault(school_id, {"enrollment": enrollment, "candidates": []})
        rec["candidates"].append((dist, hospital_id))

    candidate_sets = []
    for rec in by_school.values():
        min_dist = min(d for d, _ in rec["candidates"])
        tied = sorted({hid for d, hid in rec["candidates"] if abs(d - min_dist) <= TIE_EPSILON_M})
        candidate_sets.append((rec["enrollment"], tied))

    valid_outcomes = []
    for combo in itertools.product(*(tied for _, tied in candidate_sets)):
        outcome = {hid: {"school_count": 0, "total_enrollment": 0} for hid in all_hospitals}
        for (enrollment, _), hospital_id in zip(candidate_sets, combo):
            outcome[hospital_id]["school_count"] += 1
            outcome[hospital_id]["total_enrollment"] += enrollment
        valid_outcomes.append(outcome)

    exists = _table_exists(sandbox, TABLE)
    # weight 0: a missing table already early-returns score 0.0 below, so this
    # check would otherwise double-count on top of the other weights.
    checks.append(("output_table_exists", 0.0, exists))
    if not exists:
        labels.append("wrong_layer")
        return 0.0, checks, labels

    rows = _q(sandbox, f'SELECT hospital_id, school_count, total_enrollment FROM "{TABLE}";')
    actual = {r[0]: {"school_count": r[1], "total_enrollment": r[2]} for r in rows}

    completeness_ok = set(actual) == set(all_hospitals)
    checks.append(("all_hospitals_present", 0.30, completeness_ok))
    if not completeness_ok:
        labels.append("missing_empty_hospital")

    assignment_ok = any(
        all(hid in actual and actual[hid]["school_count"] == v["school_count"] for hid, v in outcome.items())
        for outcome in valid_outcomes
    )
    checks.append(("assignment_counts_correct", 0.30, assignment_ok))
    if not assignment_ok:
        labels.append("wrong_nearest_assignment")

    totals_ok = any(
        all(hid in actual and actual[hid]["total_enrollment"] == v["total_enrollment"] for hid, v in outcome.items())
        for outcome in valid_outcomes
    )
    checks.append(("enrollment_totals_correct", 0.30, totals_ok))
    if not totals_ok:
        labels.append("wrong_totals")

    schema_ok = {"hospital_id", "name", "school_count", "total_enrollment"}.issubset(_columns(sandbox, TABLE))
    checks.append(("schema_correct", 0.10, schema_ok))

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
