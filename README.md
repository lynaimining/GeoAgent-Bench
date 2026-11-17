# GeoAgent-Bench

GeoAgent-Bench 是面向 GIS Agent 和矿产勘查 Agent 的公开评测集，覆盖 **13 个领域、200 道题**。170 道单任务各有一个业务目标，30 道复合任务要求把多个依赖阶段连成可复核成果。第 05 类专测 MPM 成矿预测分析。

[200 道题与环境](docs/tasks/README.md) · [交互目录 HTML](docs/catalog.html) · [数据来源与许可](DATA_LICENSES.md) · [运行环境](docs/ENVIRONMENT.md) · [适配器与评测](docs/EVALUATION.md)

## 快速开始

```bash
git clone https://github.com/lynaimining/GeoAgent-Bench.git
cd GeoAgent-Bench
python -m geoagent_bench validate
python -m geoagent_bench list --domain 05
python -m geoagent_bench show G200-08-S04
python -m geoagent_bench prepare G200-08-S04 --offline --dest runs/coverage
```

Python 3.12 即可准备这道合成钻孔题。`runs/coverage/TASK_PROMPT.md` 是交给 Agent 的提示词，`inputs/` 是它的输入，成果写入 `outputs/`。阅读全文可查看[代码与成果格式](docs/EVALUATION.md)。

```bash
# 文件、向量、栅格、插值、表格、PostGIS 与 GeoBenchX 数据获取
uv sync --locked --group analysis --group postgis --group download

# 以固定版本获取上游 MPM 输入，核验文件后建立单题目录
uv run --no-sync python -m geoagent_bench prepare G200-05-S05 --dest runs/mpm-labels

# 用实际运行成果填写人工评分表
python -m geoagent_bench review-form G200-08-S04 --output runs/coverage.review.json
```

在线访问受限时，可导入已下载的上游快照。模型接口、桌面工具和付费服务由使用者配置。仓库提供离线 Python 示例与 PostGIS 示例供验收接线。[环境与数据命令](docs/ENVIRONMENT.md)。

## 覆盖范围

| 编号 | 领域 | 单任务 | 复合任务 |
|---|---|---:|---:|
| 01 | 项目数据接入与整理 | 16 | 2 |
| 02 | 空间参考与数据质量 | 16 | 2 |
| 03 | 属性查询与空间数据库 | 16 | 2 |
| 04 | 矢量空间分析与网络分析 | 20 | 3 |
| 05 | MPM 成矿预测分析 | 14 | 3 |
| 06 | 遥感与栅格分析 | 22 | 4 |
| 07 | 地球化学分析 | 12 | 2 |
| 08 | 钻孔数据与井下空间分析 | 14 | 3 |
| 09 | 三维地质与地下空间表达 | 10 | 2 |
| 10 | 空间统计与插值 | 10 | 2 |
| 11 | 块模型与资源量计算 | 6 | 1 |
| 12 | 地图制图与成果交付 | 8 | 2 |
| 13 | 技术报告与证据追溯 | 6 | 2 |
| | **合计** | **170** | **30** |

题源包含 26 道公开原题、118 道改编题、56 道新增题。原题注明题号与上游版本。公开版为 48 道涉及内部项目数据的题生成了独立的合成输入和对应参考值。与工作区版本比较成绩时应分开标注数据版本。Earth-Bench-V2 相关题目按原数据的非商业条款配置。出处及改编说明可逐题查看。[数据许可](DATA_LICENSES.md)。

## 文件说明

| 文件或目录 | 内容 |
|---|---|
| [tasks/tasks.jsonl](tasks/tasks.jsonl) | 逐题目标、输入路径、依赖、输出合同、来源和阶段 |
| [assets/manifest.json](assets/manifest.json) | 冻结文件的来源 URL、字节数和 SHA-256，以及派生数据的生成方式 |
| [geoagent_bench/](geoagent_bench/) | 下载、单题隔离准备、适配器启动、制品检查和评分 |
| [environments/postgis/](environments/postgis/) | PostGIS 初始化和场景 SQL |
| [evaluator/](evaluator/) | 200 份评分规则、确定性参考值、作者验题函数 |
| [schemas/](schemas/) · [examples/](examples/) | 提交结果的 JSON Schema 和可运行示例 |

评测提供 18 道 PostGIS 终态验证，50 道题有冻结数值或结构参考，其中 5 道可直接核对指定 JSON 字段。最终评分还考虑证据与业务约束。现有题集没有模型成绩或排行榜。[评测方法](docs/EVALUATION.md)。

## Attribution

GeoAgent-Bench is an independent evaluation suite for GIS and mineral exploration agents. Each task records the upstream revision and original item locator where applicable. Reuse the benchmark code under the MIT license and follow the relevant source terms for each data track. [Licenses and attribution](DATA_LICENSES.md).
