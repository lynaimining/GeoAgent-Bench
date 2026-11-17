"""Prepare a single task and inspect its submitted artifacts."""

import math
import tempfile
from pathlib import Path

from .common import ROOT, identity, matches, path_at, read_json, write_json

STATUSES = {"completed", "needs_clarification", "unavailable", "failed", "cancelled", "unknown"}
NUMERIC_SCHEMAS = {
    "G200-03-S07": '{"count": int, "regions": [str, ...]}。地区按名称排序，百分比另列。',
    "G200-03-S08": '{"count": int, "classes": [str, ...]}。类别按名称排序。',
    "G200-03-S10": '{"forest_pct": number}。以百分数提交。',
    "G200-03-S11": '{"Faro": number, "Beja": number, "difference_pp": number}。前两项为百分数。',
    "G200-06-S01": '{"valid_n": int, "mean": number, "rounded3": number, "denominator_zero": int}。'
                   "denominator_zero 统计整幅数据中存储值之和为零的像素数。有效样本另外按本题掩膜统计。",
}
PROFILE_NOTES = {
    "python": "Python 3.12 标准库可读取 JSON、CSV、OBJ 等文本输入。按题目实现校验、聚合或出具清单。",
    "gis": "使用输入的 CRS、几何、掩膜和单位。可使用 GeoPandas、Pyogrio、Rasterio、PyProj、"
           "NumPy 或等价工具。核验实际输出数据及元数据。",
    "analysis": "用于插值、空间统计、NetCDF、表格和数值分析。可使用 GIS 环境、NumPy、"
                "SciPy、scikit-learn、NetCDF4、openpyxl 或等价工具。",
    "postgis": "每次运行使用独立数据库。使用 BENCH_DB_DSN 或适配器提供的 SQL 工具。"
               "提交执行过的 SQL 和对象读回，保留列名、类型、SRID 与结果表名。",
    "vision": "需要能够读入原始像素的图像工具或多模态模型。附图像 ID、像素坐标、证据区域和答案。",
    "qgis": "需要可实际保存及重开工程的 QGIS。提交工程、可迁移数据和重开读回。",
    "geovis3d": "需要可实际保存及重开工程的 GeoVis3D 工具。记录应用版本、对象 ID、坐标及重开读回。",
}


def prompt_for(task, original="", *, preview=False):
    """Render the agent contract separately from evaluation materials."""
    lines = [
        f"# {task['id']} · {task['title']}", "",
        "输入读取自 inputs/。所有新建本地文件写入 outputs/。",
        "只使用本题提供的数据和工具。先核对 CRS、字段、版本、单位和运行条件。",
        "提交实际成果与读回证据。需要澄清业务条件时说明具体问题，环境缺失时列出未完成的工作。",
        "", task["goal"], "",
    ]
    if original:
        lines.extend(["## 上游题干", "", original, ""])
    elif preview and task.get("earth_original"):
        lines.extend(["执行准备时从固定版本 Earth-Bench-V2 读取原文与选项。", ""])
    if task["stages"]:
        lines += ["## 有依赖的阶段", ""]
        lines += [f"{i}. {stage}" for i, stage in enumerate(task["stages"], 1)]
        lines.append("")
    lines += ["## 输入文件", ""] + [f"- {path}" for path in task["input_paths"]] + [""]
    lines += ["## 代码与成果提交", ""] + [f"- {PROFILE_NOTES[p]}" for p in task["profiles"]]
    lines.append("- 在 outputs/result.json 填写 status、summary、metrics、artifacts、evidence 和 limitations。"
                 "如需澄清，补充 reason_code。")
    lines.append("- 使用代码时保留本次执行的脚本或 SQL 及复跑命令。使用工具时记录工具版本、参数、回执和读回。"
                 "中间结果应能通过输入文件名及参数追溯。")
    if task["named_outputs"]:
        outputs = ", ".join(task["named_outputs"])
        lines.append(f"- 完成时提交 {outputs}。在 artifacts 中登记这些文件的相对路径。")
    if task["id"] in NUMERIC_SCHEMAS:
        lines.append(f"- values.json 字段为 {NUMERIC_SCHEMAS[task['id']]}")
    if task.get("postgis"):
        contract = task["postgis"]["output_contract"]
        if contract:
            lines.append(f"- 在数据库 public schema 提交表 {contract['table']}，"
                         f"至少含列 {', '.join(contract['required_columns'])}。")
            if contract.get("srid"):
                lines.append(f"- 输出几何类型 {contract['geometry_type']}，EPSG:{contract['srid']}。")
        lines.append("- 同步提交执行结果、读回表名及证据。输出缺失条件时填写 reason_code，"
                     "可用 ambiguous_request、contradictory_constraints、missing_layer 或本题实际原因。")
    return "\n".join(lines) + "\n"


def prepare(task, inputs, destination):
    dest = Path(destination).resolve()
    if dest.exists():
        raise ValueError(f"Run directory already exists: {dest}")
    files, original = inputs.fetch_task(task)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent, prefix=".stage-") as directory:
        temp = Path(directory) / "work"
        (temp / "inputs").mkdir(parents=True)
        (temp / "outputs").mkdir()
        inputs.stage_files(files, temp / "inputs")
        (temp / "TASK_PROMPT.md").write_text(prompt_for(task, original), encoding="utf-8", newline="\n")
        write_json(temp / "TASK_CONTRACT.json", {
            "id": task["id"], "title": task["title"], "goal": task["goal"],
            "stages": task["stages"], "profiles": task["profiles"],
            "input_dir": "inputs", "output_dir": "outputs", "result": "outputs/result.json",
            "inputs": {name: identity(temp / "inputs" / name) for name in files},
            "named_outputs": task["named_outputs"],
            "expected_database_output": task.get("postgis", {}).get("output_contract"),
        })
        temp.rename(dest)
    return dest


def inspect_run(task, run):
    run = Path(run).resolve()
    contract = read_json(run / "TASK_CONTRACT.json")
    if contract["id"] != task["id"] or set(contract["inputs"]) != set(task["input_paths"]):
        raise ValueError("Staged task or input list does not match")
    issues = []
    changed = [
        name for name, meta in contract["inputs"].items()
        if not matches(path_at(run / "inputs", name), meta)
    ]
    if changed:
        issues.append(f"Changed or missing inputs: {', '.join(changed)}")
    actual = {
        file.relative_to(run / "inputs").as_posix()
        for file in (run / "inputs").rglob("*") if file.is_file()
    }
    extra = actual - set(contract["inputs"])
    if extra:
        issues.append(f"Unexpected files under inputs/: {', '.join(sorted(extra))}")
    submitted = path_at(run, "outputs/result.json")
    if not submitted.is_file():
        return {"status": "no_submission", "issues": [*issues, "Missing outputs/result.json"]}
    result = read_json(submitted)
    if not isinstance(result, dict):
        raise ValueError("result.json must contain an object")
    status = result.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        issues.append("Missing or invalid status")
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        issues.append("Missing summary")
    for key in ("metrics", "artifacts", "evidence", "limitations"):
        if not isinstance(result.get(key), list):
            issues.append(f"{key} must be an array")
    if not result.get("reason_code") and status == "needs_clarification":
        issues.append("needs_clarification requires reason_code")
    if issues:
        return {"status": "invalid_submission", "execution_status": status, "issues": issues}
    for metric in result["metrics"]:
        if not isinstance(metric, dict) or not {"name", "value", "unit"} <= set(metric):
            issues.append("Each metric requires name, value and unit")
    for item in result["evidence"]:
        if not isinstance(item, dict) or not isinstance(item.get("detail"), str) or not item["detail"].strip():
            issues.append("Each evidence entry requires a nonempty detail")
    if any(not isinstance(value, str) for value in result["limitations"]):
        issues.append("limitations entries must be strings")
    seen = set()
    for artifact in result["artifacts"]:
        if (not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str)
                or not isinstance(artifact.get("readback"), str) or not artifact["readback"].strip()):
            issues.append("Each artifact requires path and a nonempty readback")
            continue
        relative = artifact["path"]
        if relative in seen:
            issues.append(f"Duplicate artifact reference: {relative}")
        seen.add(relative)
        if not path_at(run / "outputs", relative).is_file():
            issues.append(f"Missing artifact: {relative}")
    if status == "completed":
        if not result["evidence"]:
            issues.append("Completed runs require execution evidence")
        for name in task["named_outputs"]:
            if name not in seen:
                issues.append(f"Register required artifact in result.json: {name}")
    return {"status": "invalid_submission" if issues else "ready_for_review",
            "execution_status": status, "issues": issues}


def equivalent(actual, reference):
    if isinstance(reference, bool) or reference is None or isinstance(reference, str):
        return type(actual) is type(reference) and actual == reference
    if isinstance(reference, (int, float)):
        return type(actual) in (int, float) and (
            actual == reference if type(reference) is int else math.isclose(
                actual, reference, rel_tol=1e-6, abs_tol=1e-8
            )
        )
    if isinstance(reference, list):
        return isinstance(actual, list) and len(actual) == len(reference) and all(
            equivalent(x, y) for x, y in zip(actual, reference)
        )
    return isinstance(actual, dict) and set(actual) == set(reference) and all(
        equivalent(actual[k], reference[k]) for k in reference
    )


def numeric_checks(task, run, rubric):
    if not task.get("numeric_output"):
        return None
    path = path_at(Path(run) / "outputs", task["numeric_output"])
    if not path.is_file():
        return {"reference_values_match": False, "reason": "missing values.json"}
    actual = read_json(path)
    reference = read_json(path_at(ROOT, rubric["reference_path"]))
    return {"reference_values_match": equivalent(actual, reference), "comparison": "values.json"}
