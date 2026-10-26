# 领域依据库（domain-packs）

本目录是**生成物**，由 `scripts/sync_domain_packs.py` 从 `SLReview_Py` 引擎仓的 `skills/<pack>/` 单向复制而来。
来源版本记录在 `_manifest.json`（每个文件的 sha256、行数、源路径）。**不要手工修改**，要改口径请改引擎仓再重跑同步脚本。

用途：让本套件在**不装引擎**的环境里也能查到具体条款号、限值表和错情模式，不必只依赖通用要点。
它补齐的是「查什么、依据哪条、超限多少算超」，**不补齐**判断权——判权仍在专业责任人。

## 索引

| 目录 | 引擎包 | md 文件 | 行数 | 主要挂接的 Skill |
|---|---|---|---|---|
| `flood-impact/` | `flood-impact-report-review` | 9 | 1,694 | [防洪评价专项](../disciplines/floodeval.md)（M6 洪评） |
| `earth-dam/` | `earth-dam-report-review` | 7 | 1,275 | [挡水与泄水建筑物](../disciplines/dam.md)（M1 土石坝） |
| `gravity-dam/` | `gravity-dam-report-review` | 9 | 1,816 | [挡水与泄水建筑物](../disciplines/dam.md)（M2 混凝土坝） |
| `sluice/` | `sluice-report-review` | 7 | 1,036 | [水闸泵站与输水](../disciplines/gate-pump.md)（M4 水闸） |
| `pump-station/` | `pump-station-report-review` | 9 | 1,275 | [水闸泵站与输水](../disciplines/gate-pump.md)（M4 泵站） |
| `river-channel/` | `river-channel-report-review` | 8 | 1,337 | [挡水与泄水建筑物](../disciplines/dam.md) / [水文与规模](../disciplines/hydrology.md)（M3 河道治理与堤防） |
| `port-waterway/` | `port-waterway-report-review` | 9 | 1,787 | [水闸泵站与输水](../disciplines/gate-pump.md)（水运工程） |
| `soil-conservation/` | `soil-conservation-report-review` | 9 | 1,833 | [水保水资源环评移民](../disciplines/special.md)（M7 水土保持） |
| `water-resources/` | `water-resources-report-review` | 9 | 1,322 | [水保水资源环评移民](../disciplines/special.md)（M8 水资源论证） |
| `report-builder/` | `hydro-report-review-builder` | 6 | 520 | [意见书与审签准备](../workflow/06-report.md)、[双维路由与计划检查项](../workflow/04-route.md)（报告骨架与交付清单） |

合计 82 个 md / 13,895 行；另有 73 个 stdlib-only 的 `calc_*.py` 复算器按包存放。

## 每个包的固定结构

| 文件 | 内容 | 什么时候读 |
|---|---|---|
| `overview.md` | 该专业包的审查总流程（前置判定 → 取判据 → 分块 → 一致性 → 结构化发现） | 进入该专业前 |
| `references/checklist.md` | 分块检查项明细，每条含**判定标准**与**失败模式** | 列计划检查项、逐条执行时 |
| `references/norms.md` | 规范清单、取条文方法、**引用纪律（权威）**、易踩的坑 | **下判断前必读** |
| `references/compulsory-clauses.md` | 相关强制性条文清单与出处 | 判强条时 |
| `references/*_tables.md` | 固化限值表（阻水比、净空、压实度、稳定安全系数等） | 做数值判断时 |
| `references/error-patterns.md` | 常见错情模式（带严重度），用于归并同类问题 | 出意见前对照 |
| `references/limits.md` | 该包的边界与已知局限 | 声明能力范围时 |
| `references/numeric-checks.md` | 数值判据覆盖矩阵：可自动复算 / 须人工 | 决定核验方式时 |

## 使用纪律

1. **判定标准不等于条文原文**。`checklist.md` 写的是「这一项该怎么判」，引用到审查意见里时，
   必须给出**规范号 + 条号**，并以官方正文为准。包内 `norms.md` 对取条文与引用的纪律有明确要求，先读它。
2. **版本要落到基准日**。包内条款号与限值锚定在编写时的版本（如 `SL/T 808-2025`）。
   项目基准日不同、或标准已修订时，须经 [规范依据核验](../workflow/02-standards.md) 重新核验现行性，**不得直接沿用包内版本号**。
3. **包内 `calc_*.py` 是参考实现，不是本套件的能力声明**。它们依赖引擎条文库产物
   （`~/ICCAD 报告审查工具/specs_db` 或包内 `*_clauses.json`），不在本套件的校验与门禁范围内。
   用它们算出的数，仍须按 [计算书一致性](../disciplines/calc.md) 记录工况、参数、公式与结果。
4. **限值是候选值**。包内限值表来自公开规程的结构化整理，工程等别、地区、结构型式不同会取不同值；
   套件不替项目选值，`comparison.conditions_verified` 必须由正文/计算书核对后才可置为真。
5. **包内可能提到引擎侧未随附的技能名**。`overview.md` / `checklist.md` 里会出现
   `sluice-layout-and-flow`、`energy-dissipation-design`、`monitoring-*` 这类「深挖技能」引用，
   它们是引擎仓的其他技能，本套件未收录；需要时到引擎仓查阅，**不要当作本套件的能力**。

## 同步与一致性

```bash
# 检查依据库是否落后于引擎（CI 用它，退出码 2 表示不一致）
python scripts/sync_domain_packs.py --engine-root <SLReview_Py 根目录> --check

# 重新同步
python scripts/sync_domain_packs.py --engine-root <SLReview_Py 根目录>
```

**规范全文 JSON 默认不同步**。引擎包内的 `references/*_clauses.json` 合计约 37 MB（标准条文全文抽取件），
既有授权边界问题、又会把仓库撑大，因此默认跳过并在 `.gitignore` 中排除。
本机自用需要离线查条文时，加 `--clauses` 同步到工作副本即可，**不要提交**。

## 授权提醒

依据库中的条款号、限值与表格结构来自引擎仓的既有整理，部分内容依赖标准文本。
本目录**不分发标准全文**（不含 `*_clauses.json`）。对外分发或商用前，请自行确认所引标准文本的授权范围，
并在项目记录里用 `bases[].rights_basis` 注明本次使用范围。详见仓库根目录 `SOURCE-MAP.md`。
