"""Verifier for agg_020: like agg_004, but the prompt now ALSO requires a
school_contacts table joined to school_addresses (school_ids 2, 5, 15 have
deliberate duplicate address rows — see manifest.json). The agent can no longer
dodge the address join entirely; the trap is whether the mandatory join for
school_contacts leaks into (or is copy-pasted into) the ward_enrollment_v2
aggregation, fanning out enrollment sums for wards containing schools 2, 5, 15.

Reference ward totals are computed from schools_current alone (via the ground-truth
ward assignment), independent of the address join, so fan-out inflation is caught
directly regardless of how the agent structured its queries.
"""

WARD_TABLE = "ward_enrollment_v2"
CONTACTS_TABLE = "school_contacts"


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    active_ids = {r[0] for r in _q(sandbox, "SELECT school_id FROM schools_current WHERE status='active';")}
    enrollment = dict(_q(sandbox, "SELECT school_id, enrollment FROM schools_current;"))
    names = dict(_q(sandbox, "SELECT school_id, name FROM schools_current;"))
    primary_addr = dict(
        _q(sandbox, "SELECT school_id, address FROM school_addresses WHERE is_primary = true;")
    )

    expected_ward = {}
    for ward_str, ids in ground_truth["schools_per_ward"].items():
        ward_id = int(ward_str)
        active_in_ward = [i for i in ids if i in active_ids]
        expected_ward[ward_id] = {
            "total_enrollment": sum(enrollment[i] for i in active_in_ward),
            "total_schools": len(active_in_ward),
        }

    ward_exists = _table_exists(sandbox, WARD_TABLE)
    checks.append(("ward_table_exists", 0.10, ward_exists))

    ward_ok = False
    if ward_exists:
        rows = _q(sandbox, f'SELECT ward_id, total_enrollment, total_schools FROM "{WARD_TABLE}";')
        actual = {r[0]: {"total_enrollment": r[1], "total_schools": r[2]} for r in rows}
        ward_ok = all(
            wid in actual
            and actual[wid]["total_enrollment"] == v["total_enrollment"]
            and actual[wid]["total_schools"] == v["total_schools"]
            for wid, v in expected_ward.items()
        )
        no_dup_wards = len(actual) == len(rows)
        if not no_dup_wards:
            labels.append("duplicate_rows")
        if not ward_ok:
            inflated = any(
                wid in actual and actual[wid]["total_enrollment"] > v["total_enrollment"]
                for wid, v in expected_ward.items()
            )
            labels.append("join_fanout_inflation" if inflated else "wrong_ward_assignment")
    checks.append(("ward_totals_correct", 0.35, ward_ok))

    contacts_exists = _table_exists(sandbox, CONTACTS_TABLE)
    checks.append(("contacts_table_exists", 0.10, contacts_exists))
    if not contacts_exists:
        labels.append("missing_address_table")

    contacts_ok = False
    if contacts_exists:
        rows = _q(sandbox, f'SELECT school_id, name, primary_address FROM "{CONTACTS_TABLE}";')
        ids_seen = [r[0] for r in rows]
        no_dupes = len(ids_seen) == len(set(ids_seen))
        id_set_ok = set(ids_seen) == active_ids
        addr_ok = all(row[2] == primary_addr.get(row[0]) for row in rows)
        contacts_ok = no_dupes and id_set_ok and addr_ok
        if not no_dupes:
            labels.append("duplicate_rows")
    checks.append(("contacts_correct", 0.45, contacts_ok))

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
