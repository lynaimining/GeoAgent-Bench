"""Verifier for abstain_010: the prompt says "the river" but the rivers table
has 3 rows (Main River + 2 tributaries) — there is no single correct referent.
The only correct behavior is to call submit(status="blocked", reason_code="ambiguous_request").
Grading matches on reason_code only, never on the agent's free-text note.
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
