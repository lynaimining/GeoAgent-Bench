"""Verifier for amb_017: the prompt gives a bare number "within 2" with no unit.
Confirmed against the data: interpreted as 2 metres, zero active schools qualify;
interpreted as 2 kilometres (2000m), eight do. The two readings genuinely diverge,
so silently picking either is a guess, not an inference. Correct behavior is
submit(status="blocked", reason_code="ambiguous_request").
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
