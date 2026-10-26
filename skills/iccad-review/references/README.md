# 章节索引

`iccad-review` 是单一技能，全部专业内容按章节放在本目录。**按需读，不要全量载入**：
先用 [总控](../SKILL.md) 定模块与阶段，再只读本篇用得到的章节。

## 流程章节（`workflow/`，按序推进）

| 序 | 章节 | 什么时候读 | 行数 |
|---|---|---|---|
| 1 | [资料接收与报告基线](workflow/01-intake.md) | 审查开始、补资料、换版重审 | 51 |
| 2 | [规范依据核验与检索](workflow/02-standards.md) | 要写依据、要查现行性、要判强条 | 90 |
| 3 | [审查规则编制与验证](workflow/03-rules.md) | 要把条文转成可执行判据 | 41 |
| 4 | [双维路由与计划检查项](workflow/04-route.md) | 定模块 M1~M14 与阶段，编计划项 | 91 |
| 5 | [设计回复与整改闭环复查](workflow/05-closure.md) | 收到回复、修订稿、换版 | 59 |
| 6 | [审查意见书与审签准备](workflow/06-report.md) | 出内部报告、做批注版 | 103 |
| 7 | [审查试点回测与效果评估](workflow/07-benchmark.md) | 试点验收、规则/模型改版回归 | 52 |

## 专业章节（`disciplines/`，按模块取用）

| 章节 | 覆盖 | 主要依据库 | 行数 |
|---|---|---|---|
| [水文、规模与调节计算](disciplines/hydrology.md) | 基本资料→设计洪水→调节→特征水位→规模 | 分散在河道/水资源/水闸包 | 61 |
| [挡水与泄水建筑物](disciplines/dam.md) | 土石坝、混凝土坝、溢洪道、泄洪洞；文末含河道堤防指向 | `earth-dam/`、`gravity-dam/` | 79 |
| [水闸、泵站、渠系与输水](disciplines/gate-pump.md) | 水闸 10 块、泵站 12 块、水运 12 块 | `sluice/`、`pump-station/`、`port-waterway/` | 78 |
| [工程地质与基础处理](disciplines/geotech.md) | 勘察工作量、参数链条、地基与边坡 | 无独立包 | 54 |
| [水力与结构计算书一致性](disciplines/calc.md) | 工况/参数/公式/引用四条追溯线 | 各包 `numeric-checks.md` | 61 |
| [防洪评价专项](disciplines/floodeval.md) | M6：前置六判定、12 块骨架、阻水/壅水/冲刷锚点 | `flood-impact/` | 99 |
| [水保、水资源与环评](disciplines/special.md) | M7/M8/M9 + 征地移民篇章 | `soil-conservation/`、`water-resources/` | 96 |
| [施工组织、导流与概算](disciplines/cost.md) | 导流标准、工程量四级守恒、单价与费用 | 无独立包 | 65 |
| [跨篇章接口与图文附表](disciplines/coordination.md) | 接口矩阵、编号/数量/单位/结论/体例五类一致 | — | 61 |
| [各模块候选检查项](module-matrix.md) | M1~M14 的检查骨架，路由时取用 | — | 184 |

## 通用参考（本目录根）

| 文件 | 用途 |
|---|---|
| [review-contract.md](review-contract.md) | 记录字段、状态枚举、证据格式——动笔前必读 |
| [quality-gates.md](quality-gates.md) | 阻塞规则与退出码——出稿前必读 |
| [platform-adapter.md](platform-adapter.md) | 数据边界、脱敏、宿主能力限制 |
| [ima-integration.md](ima-integration.md) | 条文原文检索接入（可选） |
| [engine-bridge.md](engine-bridge.md) | 引擎三格式导入与三条硬规则 |
| [engine-assets.md](engine-assets.md) | 章节 ↔ 引擎包 ↔ 可执行检查器映射 |
| [status-mapping.md](status-mapping.md) | 三套状态口径对照与换算 |
| [domain-packs/](domain-packs/README.md) | 10 个专业包的已校准依据库（生成物） |

## 维护约定

- 章节是**唯一内容源**：`workflow/` 与 `disciplines/` 下的文件不再带 frontmatter，不会被识别为独立技能。
- 新增章节时同步三处：[总控路由表](../SKILL.md)、本索引、`scripts/validate_skills.py` 的章节清单校验。
- 章内互链一律用相对路径（`../workflow/xx.md`、`../disciplines/yy.md`），跨到脚本用 `../../scripts/`。
