"""Verifier for amb_018: "active and closed before 2020" is self-contradictory by
definition (schools_current.status is a single active/closed flag; a school cannot
be both). This is a logical contradiction, not a data lookup, so it does not depend
on any 2020-specific column existing. Correct behavior is
submit(status="blocked", reason_code="contradictory_constraints"). Silently
returning an empty result table is graded as a failure too: recognizing a
contradiction and observing "no rows matched" are not the same thing, and a
completed status is submitted regardless of row count.
"""


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    blocked_ok = run.status == "blocked"
    checks.append(("status_is_blocked", 0.5, blocked_ok))
    if not blocked_ok:
        labels.append("returned_empty_instead_of_flagging")

    reason_ok = run.reason_code == "contradictory_constraints"
    checks.append(("reason_code_is_contradictory_constraints", 0.5, reason_ok))
    if blocked_ok and not reason_ok:
        labels.append("wrong_reason_code")

    score = sum(w for _, w, ok in checks if ok)
    return score, checks, labels
