"""Verifier for audit_024: school_directory_broken has TWO independent defects
(missing status filter -> closed schools 12/17 included; missing is_primary
filter -> duplicate rows for schools 2/5/15). A one-bug-and-stop diagnosis only
catches half the problem; this verifier requires both categories, exactly, with
no extras -- a shotgun diagnosis that lists every possible category is not
graded as thorough, it's graded as spurious.

The second defect is a duplicate-row bug caused specifically by a join fanning
out on multiple matching rows -- "join_multiplicity" is the textbook name for
exactly this failure mode (it's one of the category options the task prompt
itself offers) and is just as correct as "duplicate_rows". Confirmed live:
every one of 4 models, ~12/12 trials, independently chose "join_multiplicity"
for this defect -- treating it as wrong would have failed a universally correct
diagnosis on a labeling technicality of this verifier's own making.
"""

EXPECTED_WRONG_FILTER = {"wrong_filter"}
EXPECTED_DUPLICATE_SYNONYMS = {"duplicate_rows", "join_multiplicity"}
# Spurious-diagnosis scope is THIS task's two actual defect slots (allowing the
# duplicate-rows/join_multiplicity synonym) -- not the full category vocabulary
# the prompt's enum lists, which also includes categories that don't apply here
# (crs_error, stale_data, boundary_exclusion). Accepting any of those as "not
# spurious" would let a shotgun diagnosis that names every possible category pass.
ACCEPTABLE_CATEGORIES = EXPECTED_WRONG_FILTER | EXPECTED_DUPLICATE_SYNONYMS


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    ref_rows = _q(
        sandbox,
        "SELECT s.school_id, s.name, s.enrollment, a.address "
        "FROM schools_current s JOIN school_addresses a ON a.school_id = s.school_id "
        "AND a.is_primary = true WHERE s.status = 'active';",
    )
    expected = {r[0]: {"name": r[1], "enrollment": r[2], "address": r[3]} for r in ref_rows}

    diag_exists = _table_exists(sandbox, "audit_result")
    checks.append(("audit_result_table_exists", 0.15, diag_exists))

    found_defects = set()
    if diag_exists:
        rows = _q(sandbox, "SELECT defect_category FROM audit_result;")
        found_defects = {r[0] for r in rows}

    both_found = bool(EXPECTED_WRONG_FILTER & found_defects) and bool(
        EXPECTED_DUPLICATE_SYNONYMS & found_defects
    )
    checks.append(("both_defects_named", 0.35, both_found))
    if not both_found:
        labels.append("partial_diagnosis")

    no_spurious = found_defects.issubset(ACCEPTABLE_CATEGORIES)
    checks.append(("no_spurious_defect_categories", 0.15, no_spurious))
    if not no_spurious:
        labels.append("spurious_defect_category")

    fixed_exists = _table_exists(sandbox, "school_directory_fixed")
    checks.append(("fixed_table_exists", 0.10, fixed_exists))

    fix_ok = False
    if fixed_exists:
        rows = _q(sandbox, 'SELECT school_id, name, enrollment, address FROM school_directory_fixed;')
        actual = {r[0]: {"name": r[1], "enrollment": r[2], "address": r[3]} for r in rows}
        no_dupes = len(rows) == len(actual)
        fix_ok = no_dupes and actual == expected
    checks.append(("fixed_table_correct", 0.25, fix_ok))
    if not fix_ok:
        labels.append("fix_incomplete")

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
