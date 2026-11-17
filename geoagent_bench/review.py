"""Create a human review and compute its score from entered evidence."""

from .common import write_json


def blank_review(rubric, destination):
    if destination.exists():
        raise ValueError("Review file already exists")
    write_json(destination, {
        "task_id": rubric["task_id"], "reviewer": None, "execution_status": None,
        "core_correct": None, "critical_failures": [],
        "criteria": [dict(row, awarded=None, evidence=[], notes="") for row in rubric["criteria"]],
    })


def score_review(rubric, review):
    if review["task_id"] != rubric["task_id"] or not review.get("reviewer"):
        raise ValueError("Review must name the reviewer and match the task")
    execution = review.get("execution_status")
    if execution in {"unavailable", "failed", "cancelled", "unknown"}:
        return {"task_id": rubric["task_id"], "status": execution, "score": None, "pass": False}
    if execution not in {"completed", "needs_clarification"} or type(review.get("core_correct")) is not bool:
        raise ValueError("Record execution_status and mark whether the core result is correct")
    maxima = {info["id"]: info["points"] for info in rubric["criteria"]}
    entries = review["criteria"]
    if {entry["id"] for entry in entries} != set(maxima) or len(entries) != len(maxima):
        raise ValueError("Review requires one grade for each criterion")
    total = 0
    for row in entries:
        score = row["awarded"]
        if type(score) not in (float, int) or not 0 <= score <= maxima[row["id"]]:
            raise ValueError(f"Score outside its range: {row['id']}")
        if score > 0 and not row.get("evidence"):
            raise ValueError(f"Attach evidence for {row['id']}")
        total += score
    passed = total >= rubric["pass_rule"]["points_at_least"] and review["core_correct"] and not review["critical_failures"]
    return {"task_id": rubric["task_id"], "status": "graded", "score": round(total, 4), "pass": passed}
