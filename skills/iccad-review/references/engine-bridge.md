# 与确定性引擎的桥接（可选）

本套件不依赖任何引擎。若本机已安装 `iccad-review` 确定性扫描引擎（Python 3.10 字节码内核 + 1232 部规范注册表），
可以把它的零 Token 预扫结果导入为**候选检查项**，减少人工重复劳动。

引擎解决的问题与套件不同：

| | 引擎（`iccad-review`） | 本套件（`iccad-review-skill`） |
|---|---|---|
| 定位 | 规则可判定项的快速筛查 | 审查范围、证据、闭环与审签条件的记录体系 |
| 输出 | 命中清单（领域、强条、数值、规范号、悬赏模式） | 计划项、依据卡、规则、疑点台账、闭环记录 |
| 判定权 | 无 | 无（判权在人工） |
| 覆盖 | 规则可判定项 | 规则 + 推理 + 资料完整性 |

## 导入命令

```bash
# 1. 先跑引擎预扫（引擎自带 venv 的 3.10 解释器）
"$PY" "$ENGINE/scripts/wsl_scan.py" 报告.docx --json scan.json --md scan.md --quiet

# 2. 导入为候选检查项
python skills/iccad-review/scripts/import_scan.py scan.json \
       --document 报告.docx --out review/scan-imported.json \
       --name "XX水库初设" --module M1 --stage preliminary --grade III --baseline-id 送审稿V1

# 3. 校验导入结果（预期无结构错误，仍有阻塞项）
python skills/iccad-review/scripts/validate_review.py review/scan-imported.json
```

## 字段映射

| 引擎字段 | 记录字段 | 说明 |
|---|---|---|
| `scan.primary_domain` | `project.project_type` / `project.module` | 领域→模块为粗映射（土石坝→M1、水闸→M4…）。**已知存在偏差**（灌区渠系常被判为水闸），计划口径以 `iccad-route` 判定为准，`scope_ref` 保留引擎原判 |
| `scan.errors[].category` | `checks[].engine_ref` | 引擎类别名，作为检查器来源 |
| `scan.errors[].quote` | `checks[].evidence[].excerpt` | **仅逐字引用**；`quote` 为空时不造证据 |
| `scan.errors[].location` | `checks[].evidence[].locator` | 空则记「全文」，须人工定位 |
| `scan.errors[].explanation` | `checks[].reason` / `findings[].observation` | 截断保留，原文可回查引擎输出 |
| `scan.errors[].suggestion` | `findings[].suggested_action` | — |
| `scan.errors[].is_suggestion` | `findings[].priority` | 建议类→`P3`，其余→`P2`（**不自动产生 P1**） |
| `scan.errors[].finding_type=missing` | `findings[].kind` | → `missing_information` |
| `spec_codes[].valid=false` | 独立的 `rule_deviation` 检查项 | 规范号被替代/无效/未收录 |
| `scan.suppressed` | — | 已被误报免疫过滤的条数，导入时丢弃，需在报告中说明 |

## 三条硬规则

1. **引擎命中不等于疑点定稿**。导入的 `findings` 一律 `confidence=medium`、`review.status=pending`；
   人工复核后改 `confidence`、补 `basis_ids` 与处置记录。
2. **无引文不补造**。`quote` 为空时状态记 `insufficient_input`，理由写明「引擎命中但无可定位片段」。
   这会在 `--gate` 处阻塞，直到人工定位或明确缩范围。
3. **引擎无依据卡**。导入记录 `bases` 为空，`origin=engine` 的检查项以 `engine_ref` 代替规则；
   一旦人工确认某条成立，必须补 `bases` 与 `rules`（走 `iccad-standards` + `iccad-rule-author`），
   否则该条无法作为「有依据的审查意见」提交。

## 不导入的部分

- 引擎的「经验要点清单」（`knowledge`）：属于提示性材料，不构成检查项；由各专业技能按需查阅。
- 引擎的领域判定与等别判定：仅作参考，不写入 `project.grade`。
- 引擎的批注版与意见书：本套件用自己的 `render_report.py` 与 `iccad-report` 生成，避免两套口径。

## 许可提醒

引擎 `engine/` 内含字节码与授权模块，**有许可约束**。自用可整包复制；对外分发只发不含 `engine/` 的流程版。
本套件本身不含任何引擎代码，可在无引擎环境下独立运行。
