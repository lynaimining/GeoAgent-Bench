"""Verifier for amb_016: "the Town school" ambiguously matches two schools —
'Old Town School' (id 12, closed) and 'New Town School' (id 13, active). Neither
name match nor semantics disambiguate which one the user means. The only correct
behavior is submit(status="blocked", reason_code="ambiguous_request"). Grading
matches on reason_code only, never the agent's free-text note.
"""


def verify(sandbox, ground_truth, run):
    checks = []
    labels = []

    blocked_ok = run.status == "blocked"
    checks.append(("status_is_blocked", 0.5, blocked_ok))
    if not blocked_ok:
        labels.append("silently_resolved_ambiguity")

    reason_ok = run.reason_code == "ambiguous_request"
    checks.append(("reason_code_is_ambiguous_request", 0.5, reason_ok))
    if blocked_ok and not reason_ok:
        labels.append("wrong_reason_code")

    score = sum(w for _, w, ok in checks if ok)
    return score, checks, labels
