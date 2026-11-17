# 环境与输入准备

从仓库根目录执行命令。基础控制器支持 CPython 3.12 和 3.13。`uv.lock` 固定 Python 地学库及其依赖。各题的 `profiles` 指定推荐环境，实际 Agent 可使用满足同一合同的 GIS 工具。

| Profile | 安装 / 服务 | 对应任务 |
|---|---|---|
| `python` | CPython 3.12+，标准库 | CSV、JSON、OBJ、钻孔区间、分组和证据清单 |
| `gis` | `uv sync --locked --group gis` | GeoPandas、Pyogrio、Shapely、PyProj、Rasterio、NumPy。用于空间读写、几何处理、投影和栅格计算，也用于派生输入生成 |
| `analysis` | `uv sync --locked --group analysis` | 增加 SciPy、scikit-learn、NetworkX、Matplotlib、NetCDF4、openpyxl 与 Pillow |
| `postgis` | `uv sync --locked --group postgis`，Docker Linux 容器 | PostgreSQL 16 / PostGIS 3.4，固定 Linux/amd64 镜像。Docker Desktop 在 Windows/macOS 需启动 Linux 容器引擎 |
| `vision` | 可传入原图像的视觉工具或多模态模型 | 保留原始像素坐标、图像 ID 与人工视觉复核 |
| `qgis` | QGIS 3.40 LTR 或兼容版本，具有保存和重开工程的工具 | 记录 QGIS 版本、工程文件和新目录重开回读 |
| `geovis3d` | 已安装且接线可用的 GeoVis3D | 记录应用与工具版本、对象数、坐标、可见性和相机。控制器接收实际产物与回执 |

```bash
uv sync --locked --group analysis --group postgis --group download
uv run --no-sync python -m geoagent_bench validate
uv run --no-sync python -m geoagent_bench list --profile postgis
docker version
```

`--group download` 安装 `gdown`，用于 GeoBenchX 的作者网盘。已取得对应 `Data.zip` 时，可直接传入 `--geobenchx-archive /path/to/Data.zip`。文件校验失败时先核对下载版本，再重试。Windows PowerShell 下可使用绝对路径并加引号。

## 单题下载、全量准备和离线重放

```bash
# 从固定上游发布位置下载一个任务需要的输入
uv run --no-sync python -m geoagent_bench fetch --task G200-01-S01

# 批量准备 MPM 数据到本机缓存
uv run --no-sync python -m geoagent_bench fetch --domain 05

# 使用已下载的上游快照，全量校验并生成派生文件
uv run --no-sync python -m geoagent_bench fetch --all --offline --library "/path/to/source-snapshots" --accept-noncommercial

# 只使用准备完成的缓存
uv run --no-sync python -m geoagent_bench prepare G200-05-C02 --offline --dest runs/mpm-oof
```

默认缓存为 `.cache/`。`--cache` 可指定独立磁盘。`--library` 下各相对路径载于 `assets/manifest.json` 的 `library_path`，例如 `GABench/dataset/sn_w_minoccs.gpkg`、`GeoBenchX-inputs/Data.zip`、`Earth-Bench-V2/data/question129/...`。可下载单个任务所需数据。全量准备会读取约 1.2 GB 的上游压缩档案以及各任务直接输入，建议准备至少 4 GB 空间供缓存与运行目录使用。

`fetch --all` 默认跳过使用 Earth-Bench-V2 的题目，并列出被跳过的 ID。需要这些题时先按 [数据许可](../DATA_LICENSES.md) 核对用途。一个任务可从共享缓存取数据，每次评测使用独立准备出来的目录。

【方法来源】[uv 锁定说明](https://docs.astral.sh/uv/concepts/projects/sync/) · [PostGIS 镜像](https://github.com/postgis/docker-postgis) · [GeoAgentEval 环境](https://github.com/hsd2514/geoagenteval/tree/3da32ce6eb13dac8e0ac263e1e9830da67b8a56b)
