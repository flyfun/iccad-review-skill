# 引擎能力与资产映射

本文件说明 `SLReview_Py` 确定性引擎能提供什么、这些能力落在本技能的哪一章上、以及怎么调用。
**本套件不依赖引擎**：无引擎时依据库（`domain-packs/`）仍可用，只是少了自动化预扫。

## 三层分工

| 层 | 谁做 | 产出 | 判权 |
|---|---|---|---|
| **规则可判定层** | 引擎（零 Token） | 目录比对、复算参数核对、结论完整性、工程量投资、批复一致性、数值阈值、强条、规范号核验 | 无 |
| **依据层** | `domain-packs/`（引擎整理，随套件分发） | 检查清单、强制条文、限值表、错情模式、引用纪律 | 无 |
| **流程与判权层** | 本技能 16 章 + 模块矩阵 | 范围、计划项、依据卡、疑点台账、闭环、审签条件 | **人工** |

引擎负责「把规则能算的算出来」，依据库负责「依据哪一条、限值多少」，套件负责「谁在什么时候、基于什么证据、下了什么处置」。
三层都不出「工程通过审查」的结论。

## 引擎能力清单

### 1. 确定性判定层（11 项，零 Token）

| 判定方式 | 覆盖检查项 | 实现要点 |
|---|---|---|
| `toc-match` 目录比对 | 报告类型与目录（块1-1） | 报告目次 vs SL/T 808 附录 B 三套目录（B.1 综合 / B.2 河道 / B.3 蓄滞洪区），标题字符集合相似度贪心匹配；不涉蓄滞洪区时自动排除相关专章 |
| `param-audit` 复算参数核对 | 块5-3 / 5-4 / 5-7 / 6-13 / 9-9 / 11-6 | 核对复算所需参数与成果是否齐备，四态：齐备→符合；填「/」→不符合（该算未算）；有章节无成果→不符合；整块没有→缺失 |
| `conclusion-audit` 结论核对 | 块12-8 / 12-7 | 10.0.1 九项、10.0.5 三措辞逐项核对，截断到下一章防止附件表格污染 |
| `section-audit` 章节核对 | 块12-6 工程量与投资、块1-6 与批复一致性 | 按报告类型取对应条款（B.1 8.3 / B.2 7.3 / B.3 6.3），核对章节与投资栏 |

规则判定的结果在记录里带 `method`（如 `clause-verdict:块9-7@param-audit`），
可与模型判定的条目区分开——这一点在报告和复核时都要保留，**不要把规则结论写成模型结论**。

### 2. 数值与条文层（零 Token）

| 检查器 | 数量 | 作用 |
|---|---|---|
| `numerical_checker` | 95 条阈值项 | 按工程等别/结构型式取阈值做数值比较（堤顶宽、超高、压实度、稳定安全系数等） |
| `mandatory_clause_checker` | 登记式触发 | 强制性条文触发条件匹配，判定是否属强条范畴 |
| `cross_spec_validator` | 登记式触发 | 跨规范引用一致性 |
| `spec_registry` | 1,222 部规范 | 规范号有效性、现行/被替代/未收录 |
| `unit_format_checker` / `table_consistency_checker` / `formula_checker` | — | 单位口径、表格自洽、公式与结果一致 |

### 3. 逐项判词层（需 LLM，产生 Token）

`clause_verdict` 对检查清单逐项给出 **符合 / 不符合 / 缺失 / 不适用 / 待核**，
并带条文依据、报告原句、严重度、整改建议。它先做确定性判定（第 1 层），判不了的才走检索 + 模型。
v26 的实测：90 项检查项中「待核」为 0，依据校验 90/90。

## 章节 ↔ 引擎包映射

| 章节 | 模块 | 引擎包（`domain-packs/` 目录） | 规模 |
|---|---|---|---|
| [防洪评价专项](disciplines/floodeval.md) | M6 | `flood-impact/` | 9 md / 1,694 行 |
| [挡水与泄水建筑物](disciplines/dam.md) | M1 | `earth-dam/` | 7 md / 1,275 行 |
| [挡水与泄水建筑物](disciplines/dam.md) | M2 | `gravity-dam/` | 9 md / 1,816 行 |
| [挡水与泄水建筑物](disciplines/dam.md)、[水文与规模](disciplines/hydrology.md) | M3 | `river-channel/` | 8 md / 1,337 行 |
| [水闸泵站与输水](disciplines/gate-pump.md) | M4 水闸 | `sluice/` | 7 md / 1,036 行 |
| [水闸泵站与输水](disciplines/gate-pump.md) | M4 泵站 | `pump-station/` | 9 md / 1,275 行 |
| [水闸泵站与输水](disciplines/gate-pump.md) | 水运 | `port-waterway/` | 9 md / 1,787 行 |
| [水保水资源环评移民](disciplines/special.md) | M7 | `soil-conservation/` | 9 md / 1,833 行 |
| [水保水资源环评移民](disciplines/special.md) | M8 | `water-resources/` | 9 md / 1,322 行 |
| [意见书与审签准备](workflow/06-report.md)、[双维路由与计划检查项](workflow/04-route.md) | 通用 | `report-builder/` | 6 md / 520 行 |

**没有对应引擎包的模块**（M5 灌区、M9 环评/移民、M10 安全鉴定、M11 变更、M12 规划同意书、
M13 河湖健康、M14 幸福河湖）：依据由 [规范依据核验](workflow/02-standards.md) 现场核验，检查项由 [双维路由与计划检查项](workflow/04-route.md) 按模块矩阵生成。
这些模块**不要**硬套洪评或土石坝清单——专业口径不同。

## 调用方式

### 一键：清单核对 + 导入（推荐）

```bash
python skills/iccad-review/scripts/engine_run.py 报告.docx \
       --engine-root <SLReview_Py 根目录> --out review/imported.json
```

零 Token，约 7 秒 / 90 项（实测：18k 字洪评报告）。产出的 `review.json` 含检查项、候选疑点、待核依据卡。

### 分步：先看引擎输出，再决定导入哪部分

```bash
# 清单覆盖度（3 态）
<引擎 python> <ENGINE>/tools/checklist_audit.py 报告.docx --json audit.json --out audit.md

# 逐项条文判词（5 态，需 key；先用 --dry-run 不花钱看检索结果）
<引擎 python> <ENGINE>/tools/clause_verdict.py 报告.docx --json verdicts.json --out verdicts.md --dry-run

# 导入（自动识别三种格式）
python skills/iccad-review/scripts/import_scan.py audit.json --document 报告.docx --out review/x.json
```

`--engine-root` 也可用环境变量 `ICCAD_ENGINE_ROOT`。引擎有 `.venv` 时脚本自动用它，
避免引擎依赖（PyYAML / python-docx / jieba）与本机环境冲突。

## 同步依据库

依据库是生成物，引擎改口径后必须重同步，否则套件引用的条款会过期。

```bash
python scripts/sync_domain_packs.py --engine-root <SLReview_Py 根目录>          # 同步
python scripts/sync_domain_packs.py --engine-root <SLReview_Py 根目录> --check  # 比对（CI 用）
```

规范全文 JSON（约 37 MB）默认不同步，本机自用可加 `--clauses`，**不要提交**。

## 已知偏差（复核时优先看）

| 现象 | 原因 | 处置 |
|---|---|---|
| 灌区渠系报告被判成「水闸」 | 引擎按关键词判领域 | 模块以 [双维路由与计划检查项](workflow/04-route.md) 判定为准，`scope_ref` 保留引擎原判备查 |
| 「部分覆盖」占比高（实测 35/90） | 覆盖判定是**要素字面命中**，不看论证质量 | 部分覆盖一律 P3 且 `confidence=low`，须人工看原文确认是否真缺 |
| 「覆盖」不等于「合规」 | 同上：命中关键词 ≠ 论证成立 | 覆盖项只记 `no_signal`，**不得**写成「符合规范」 |
| 工程等别未知时阈值失效 | 阈值按等别取值 | 等别未知时数值项记 `insufficient_input`，不猜等别 |

## 许可提醒

依据库中的条款号、限值与表格结构来自引擎仓的既有整理，部分依赖标准文本。
套件**不分发标准全文**。对外分发或商用前自行确认引用标准文本的授权范围，
并在项目记录里用 `bases[].rights_basis` 注明本次使用范围。详见根目录 `SOURCE-MAP.md`。
