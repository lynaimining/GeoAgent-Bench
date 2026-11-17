# 从题目到评分

`tasks/tasks.jsonl` 是任务定义。`assets/manifest.json` 固定输入及来源。`prepare` 创建输入文件副本、`TASK_PROMPT.md` 和 `TASK_CONTRACT.json`。复合任务按题目所列顺序交付中间成果，说明后续步骤消费了哪个版本。使用同一版本的题目、输入身份与评分标准后再比较 Agent。

## 适配器

每次运行选用自己的 Agent 入口。`run` 在该次准备好的工作目录内启动命令，把以下环境变量提供给适配器。使用实际有权限的工具读取输入、执行计算并写入输出。

| 变量 | 内容 |
|---|---|
| `BENCH_TASK_ID` | 当前题号 |
| `BENCH_PROMPT` | Agent 提示词的路径 |
| `BENCH_TASK_CONTRACT` | 输入文件身份和输出合同 |
| `BENCH_INPUT_DIR` / `BENCH_OUTPUT_DIR` | 当前题的读与写目录 |
| `BENCH_DB_DSN` | PostGIS 题才设置。回环地址和限权测试用户凭据 |

命令由控制器直接启动。安装态 Agent 可通过文件适配器接入，或由人工在桌面应用中按题干运行。对需要隔离的评测，运行适配器时使用独立容器、虚拟机或工具权限，允许读取单题输入和提示词并写入该题输出。文件准备程序本身只负责材料布置。公开验题数据、代码、其他任务缓存和控制器回执应留在 Agent 可见范围外。

```bash
# 在仓库目录执行。示例把实际 CSV 覆盖率计算写进单题目录。
python -m geoagent_bench prepare G200-08-S04 --offline --dest runs/coverage
python -m geoagent_bench run G200-08-S04 --work runs/coverage --adapter python /absolute/path/GeoAgent-Bench/examples/interval_coverage.py
python -m geoagent_bench inspect G200-08-S04 --work runs/coverage

# SQL 示例需要 Docker 和 postgis Python 依赖组。
uv run --no-sync python -m geoagent_bench prepare G200-04-S01 --offline --dest runs/river
uv run --no-sync python -m geoagent_bench run G200-04-S01 --work runs/river --adapter python /absolute/path/GeoAgent-Bench/examples/postgis_flood.py
```

用一个新的 `--dest` 重跑。长任务可通过 `--timeout 1800` 调整控制器等待时间，单位为秒。控制器收集退出状态、耗时和制品检查，回执置于工作目录同级 `<name>.controller/`。取消或超时后根据应用和工具的实际回执判定，状态 `unknown` 用于不能核对终态的操作。

## 成果和代码

提交 `outputs/result.json`，符合 [JSON Schema](../schemas/result.schema.json)。`artifacts[].path` 相对于 `outputs/`。`metrics` 中保留量纲。`evidence[].detail` 写观测到的事实，优先关联具体文件、数据字段、工具版本、运行参数和回执。输入引用采用相对于 `inputs/` 的路径。执行了脚本或 SQL 时提交实际执行版本和命令，桌面操作提交工程、导出文件与重开证据。

```json
{
  "status": "completed",
  "summary": "按题目约定核对结果并保存输出。",
  "metrics": [{"name": "rows", "value": 5, "unit": "rows"}],
  "artifacts": [{"path": "coverage.csv", "readback": "已重新读取表头与 5 条记录"}],
  "evidence": [{"detail": "对每孔区间排序并求并集", "tool": "Python csv"}],
  "limitations": []
}
```

`needs_clarification` 要有 `reason_code` 和具体缺口。`unavailable` 表示缺少环境或可用工具。业务题中预设的澄清结果可以按要求通过，环境未就绪的任务单列。

## 如何打分

| 检查 | 范围 |
|---|---|
| 文件与输出合同 | 每题检查准备的输入是否变化、结果状态、已登记制品和明确的输出文件是否存在 |
| PostGIS 终态 | 18 题使用原作者验题器，在本次独立数据库上检查输出表、几何及应澄清状态。终态分和本基准的人工评分分别记录 |
| 数值参考 | 50 题有独立参考 JSON，供对照关键量与实际成果。5 题的 `values.json` 指定可直接比较的键 |
| 视觉与应用回读 | 5 题核查图片证据与上游选项，4 题必须检查真实桌面操作结果 |
| 专业复核 | 200 题各有 100 分标准，核查计算与解释、业务约束、真实执行、代码/工具参数和来源 |

```bash
python -m geoagent_bench review-form G200-08-S04 --output runs/coverage.review.json
# 核查实际运行结果，填写 reviewer、execution_status、core_correct、各项 awarded 和 evidence。
python -m geoagent_bench score G200-08-S04 --review runs/coverage.review.json
```

通过要求分数至少 80、实际核心结果正确且无关键失败。测试基础设施的成功不能代替 Agent 成绩。`tasks/grouped_splits.json` 列出上游源题或输入共享的题组，划分开发与评测集时按组切分并记录使用的 ID。梯度 1–3 为设计上的任务复杂度，后续实验可报告每档的实际结果。
