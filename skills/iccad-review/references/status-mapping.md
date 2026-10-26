# 三套状态口径对照

同一份报告，引擎与套件会用不同的词说「这一项怎么了」。三套口径各自服务于不同环节，
**不能混用**，也不能直接相等。本文件是唯一对照表；`import_scan.py` 的映射实现必须与本文一致，
改代码时同步改本文。

## 三套口径

| 口径 | 来源 | 取值 | 用途 |
|---|---|---|---|
| **判词 5 态** | 引擎 `tools/clause_verdict.py` | 符合 / 不符合 / 缺失 / 不适用 / 待核 | 对单个检查项下条文级判词 |
| **覆盖 3 态** | 引擎 `tools/checklist_audit.py` | 覆盖 / 部分覆盖 / 缺失 | 报告是否**提到**该检查点（要素字面命中） |
| **记录 6 态** | 本套件 `review-contract.md` | evaluated / not_applicable / insufficient_input / unsupported / unverified_basis / error | 审查台账中一条 check 的执行状态 |

口径差异的根源：

- **覆盖 3 态只看「有没有写」，不看「写得对不对」**。它便宜（零 Token），但会把「有章节、无论证」判成覆盖。
- **判词 5 态看「写得对不对」**，需要条文依据，可能产生 Token 消耗。
- **记录 6 态关心的是「这一项到底做完没有、依据够不够」**，所以它把「引擎有结论但引文不可信」单独拎成 `insufficient_input`。

## 判词 5 态 → 记录 6 态

| 引擎判词 | 条件 | check.status | result | 疑点 | 优先级 | 置信度 |
|---|---|---|---|---|---|---|
| 符合 | — | `evaluated` | `no_signal` | 无 | — | — |
| 不符合 | 引文存在且 `quote_verified=true`，依据 `citation_verified=true` | `evaluated` | `signal` | `rule_deviation` | 重大/一般→`P2`，建议→`P3` | `medium` |
| 不符合 | 引文缺失，或 `quote_verified=false` | `insufficient_input` | null | 无 | — | — |
| 缺失 | — | `evaluated` | `signal` | `missing_information` | 重大/一般→`P2`，建议→`P3` | `medium` |
| 不适用 | — | `not_applicable` | null | 无 | — | — |
| 待核 | — | `unverified_basis` | null | 无 | — | — |

**为什么「不符合 + 引文不可信」降成 `insufficient_input`**：契约硬规则是「无引文不补造」。
引擎说「不符合」但拿不出可校验的报告原句，等于没有证据；写成疑点就是让复核者去追一条凭空的意见。
降级后它会出现在「未求值项」清单里阻塞审签，逼出人工定位——这正是我们要的效果。

**为什么「缺失」可以带证据**：缺失的证据不是报告原文，而是**检索范围**
（「全文 18,372 字；命中要素 0 项；未命中要素：阻水比、河槽、滩地」）。
这符合契约对 `missing_information` 的要求——「应提供该资料」的要求 + 已检索范围。
`locator` 固定写 `全文（未命中）`，`excerpt` 以「检索范围：」开头，**不得**伪装成原文摘录。

## 覆盖 3 态 → 记录 6 态

| 引擎核对 | check.status | result | 疑点 | 优先级 | 置信度 |
|---|---|---|---|---|---|
| 覆盖 | `evaluated` | `no_signal` | 无 | — | — |
| 缺失 | `evaluated` | `signal` | `missing_information` | `P2` | `medium` |
| 部分覆盖 | `evaluated` | `signal` | `missing_information` | `P3` | `low` |

**「部分覆盖」为什么也产疑点**：它表示有章节但要素不全，属于「论证不足」一类，
按 P3（表达与论证完整性）登记，`confidence=low`，让复核者按原文判断是否真缺。
实测一份 18k 字洪评报告，90 项里 55 覆盖 / 35 部分覆盖 / 0 缺失——如果部分覆盖不产疑点，
就等于宣称 90 项全过，明显失真。

## 三条禁止事项

1. **不得把「覆盖」写成「符合规范」**。覆盖是字面命中，`result=no_signal` 只表示「引擎未在此项报出问题」，
   不表示论证成立。审查意见里禁止出现「引擎判定符合」这种转述。
2. **不得把「待核」改写成「不符合」**。待核的唯一含义是「条文或事实前提不足，判不了」，
   对应记录态 `unverified_basis`，处置是补依据或缩范围，不是定缺陷。
3. **不得把「重大」直接升成 `P1`**。引擎的严重度是模型判断，`P1` 是人工的注意力分流
   （防洪安全、结构安全、强制性条文、关键结论链）。导入时最高 `P2`，严重度写进 `observation`，
   由复核者决定是否升 P1。**自动产生 P1 会让门禁被几十条待核项堵死，反而掩盖真正的安全问题。**

## 依据卡的处理

引擎给出的条款锚点（`spec_code` + `clause_id`）导入为 `authority=unknown`、`status=unknown` 的依据卡，
并挂到疑点上（`basis_ids`）。这是**降低人工找依据的成本**，不是把依据变成已核验。

升为正式依据的路径（由 [规范依据核验](workflow/02-standards.md) 完成）：

```
引擎条款锚点(unknown) → 查到官方来源与实施日期 → status=effective + authority=official
                                        ↘ 查到已被替代 → status=superseded + transition_ref
                                        ↘ 查不到        → 保持 unknown，该项记 unverified_basis
```

依据卡 `status=unknown` 时，与之关联的规则必须 `draft`；但 `origin=engine` 的 check
可以保持 `evaluated`（校验器对引擎来源豁免 rule/basis 前置条件），因为它的判定依据是 `engine_ref`。

## 人工复核后的回写

| 人工处置 | 记录动作 | 引擎侧动作 |
|---|---|---|
| 确认成立 | `finding.review.status=adopted`，补 `bases`（升 effective）与 `rules` | 无需动作 |
| 确认误报 | `finding.review.status=not_applicable`（附理由与本轮 `baseline_id`） | 写入引擎误报库（`config/fp_blacklist.json`），避免下轮重复 |
| 判不了 | `finding.review.status=undetermined` | 保持原状，下轮重新判 |
| 已整改 | `closure.status=closed` + 本轮基线复查证据 | 重跑引擎，对比命中变化 |

**误报必须回写引擎**，否则每轮都会重现同一批噪声，人工复核成本不会下降。
