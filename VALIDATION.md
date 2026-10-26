# 验证记录

## 本次验证范围

**只有合成流程与脚本行为**。没有真实项目盲测，因此不提供检出率、漏报率或节时承诺。
示例中的依据编号（`EX-` 前缀）、数值与人工记录全部虚构。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-24 首次；2026-10-26 依据库与引擎桥改造后复验 |
| 系统 | Windows 10/11（Git Bash） |
| Python | 3.10+（脚本仅用标准库） |
| 依赖 | 无第三方依赖 |

## 执行的检查

```bash
python scripts/validate_skills.py
python skills/iccad-review/scripts/self_check.py
python skills/iccad-review/scripts/validate_review.py skills/iccad-review/assets/example-review.json
python skills/iccad-review/scripts/validate_review.py skills/iccad-review/assets/example-review.json --gate
python skills/iccad-review/scripts/validate_review.py skills/iccad-review/assets/example-complete.json --gate
python skills/iccad-review/scripts/render_report.py skills/iccad-review/assets/example-review.json --verify-files --output examples/示例审查意见书.md
python skills/iccad-review/scripts/ima_probe.py          # 无有效凭据时预期退出 2
```

## 结果

| 检查 | 预期 | 实测 |
|---|---|---|
| 技能目录/元数据/引用/章节索引一致性 | 1 skill、0 问题 | 通过 |
| 合成自检 `self_check.py` | 30 项全通过 | 30/30 |
| `example-review.json` 结构校验 | 退出码 0 | 0 |
| `example-review.json --gate` | 退出码 3（存在待复核与未闭环） | 3 |
| `example-complete.json --gate` | 退出码 0（闭环齐备） | 0 |
| 篡改哈希 | 被 `--verify-files` 拒绝 | 拒绝 |
| 单位换算不一致 | 被数值复算拒绝 | 拒绝 |
| 计划项被删除 | 计为阻塞而非静默通过 | 阻塞 |
| draft 规则用于已求值检查 | 报结构错误 | 错误 |
| 引擎导入（无引文命中） | 记为 `insufficient_input`，不补造引文 | 符合 |
| 报告渲染 | 七个章节齐全 | 齐全 |
| ima 探针（凭据失效场景） | 报 `credential_invalid` 并给出处置提示，退出 2 | 符合 |
| `--engine-rename` 冲突避让 | 引擎目录改名为 `iccad-engine`、frontmatter 同步、套件正常安装、`--check` 0 问题 | 通过（临时目录模拟 + 本机真实安装各一次） |

## 单技能化重构验证（2026-10-26）

把 0.x 的 16 个分散技能收编为 `iccad-review/references/` 下的章节，重跑全部校验。

| 检查 | 命令 | 实测 |
|---|---|---|
| 结构校验（新增章节索引、孤儿章节、frontmatter 混入检查） | `validate_skills.py` | 1 skill / 16 章 / 0 问题 |
| 负向测试：塞入孤儿章 + 带 frontmatter 的章节 | `validate_skills.py` | 报出 5 条问题（未被路由、未进索引、不得带 frontmatter） |
| 合成自检 | `self_check.py` | 30/30 |
| 章节内全部相对链接可解析 | 遍历 `workflow/`、`disciplines/` 的 `](...)` | 0 断链 |
| 安装往返 + 旧目录清理 | `install.py --target … --prune-legacy` | 装入 1 个技能；3 个旧目录移到 `.iccad-legacy-<时间戳>/` |
| 依据库与引擎一致 | `sync_domain_packs.py --check` | 未受影响，10 包一致 |

内容零删减：迁移前 16 个技能合计 1,405 行，迁移后 16 章 + 模块矩阵合计 1,325 行，差额 80 行正好是 16 ×（4 行 frontmatter + 1 行空行），正文一行未删；跨技能引用改写成章节相对链接，章名、表格、清单条目全部保留。

## 本轮增量验证（2026-10-26）

依据库同步与引擎桥改造后重跑，全部在本机实测。

| 检查 | 命令 | 实测 |
|---|---|---|
| 依据库与引擎一致 | `sync_domain_packs.py --engine-root … --check` | 10 包 / 168 文件 / 引擎 v26.0.0，一致 |
| 结构校验（含章节索引、依据库清单、相对链接、资产 JSON） | `validate_skills.py` | 1 skill / 16 章 / 0 问题 |
| 合成自检 | `self_check.py` | 30/30 |
| 端到端：引擎清单核对 + 导入 | `engine_run.py 洪评报告.docx --engine-root …` | 18,372 字报告 / 90 项 / 55 覆盖 · 35 部分覆盖 · 0 缺失 / 依据覆盖 100%，耗时 7.4 s、零 Token |
| 端到端产出的记录校验 | `validate_review.py .work/e2e/review.json` | 结构错误 0；阻塞项仅为「环境未核验 / 疑点待复核 / 闭环未闭 / 结论待填」 |
| 改造前的失败路径 | 把引擎清单核对输出喂给旧 `import_scan.py` | 0 条疑点，仅一条「引擎未返回任何命中」——本轮已修复并有回归用例 |

端到端跑的是真实洪评报告（讷河市后齐地营子沟两座桥梁防洪评价报告），
仅用于验证脚本链路，**不构成对该报告的任何审查结论**。

## ima 接入验证

| 通路 | 验证内容 | 结果 |
|---|---|---|
| A 宿主连接器 | 调用连接器的知识库列表与检索接口 | 通过：可列出知识库并检索到规范文件（GB 50987-2014、SL 104-2015、施工导流设计导则等） |
| B OpenAPI 凭据 | 本机 `~/.config/ima/` 存在 client_id / api_key，调用返回 HTTP 401 / `code 200002`（`skill auth failed`） | 属**凭据失效**，不是脚本缺陷；探针正确识别并给出重新生成指引 |
| B 成功分支 | 用有效密钥跑通列表与检索 | **未在本机验证**（本地密钥已失效），需有效凭据后复测 |
| C 引擎 CLI | 与 B 共用凭据与接口 | 依赖 B，未单独验证 |

结论：ima 接通的判据是「能列出知识库且能检索到文件」，两条通路都有可行路径；
本机脚本侧目前的阻塞点是密钥失效，按 `references/ima-integration.md` 的错误码表处理即可。

## 自检覆盖的行为

`self_check.py` 对下列行为做了正反两向验证：

1. 不完整记录：结构有效、审签阻塞。
2. 完整记录：结构有效、审签放行。
3. 文件哈希被篡改 → 拒绝。
4. 数值归一结果与单位换算不符 → 拒绝。
5. 计划项缺执行记录 → 阻塞。
6. `draft` 规则被用于 `evaluated` → 结构错误。
7. 引擎命中但无引文 → `insufficient_input`，证据为空。
8. 引擎导入的疑点全部 `review.status=pending`、`confidence≤medium`。
9. 三种引擎产物的格式自动识别（判词 / 清单核对 / 旧命中清单）。
10. 判词 5 态 → 记录 6 态的映射（符合→`no_signal`、不适用→`not_applicable`、待核→`unverified_basis`）。
11. 判词「不符合」但引文未校验 → `insufficient_input`，且**不产生**疑点。
12. 判词「缺失」→ `missing_information` 疑点。
13. 引擎标「重大」**不会**自动升成 `P1`。
14. 引擎条款锚点落成 `authority=unknown`/`status=unknown` 的依据卡，`level` 由规范号推导。
15. 缺失类证据只写检索范围（`locator=全文（未命中）`），不伪装原文。
16. 清单核对「缺失」必须变成疑点（回归守卫：改造前此路径产出 0 条疑点）。
17. 清单核对「部分覆盖」→ `P3`/`low`，「覆盖」→ `no_signal`。
18. 渲染结果包含全部必需章节。

## 未验证

- 真实报告上的检出率、误报率、覆盖完整性。
- ima 检索在**有效凭据**下的成功分支（列表、检索、跨库遍历）与限流表现。
- DWG/DXF 图元级核对（无解析器，一律 `unsupported`）。
- 扫描件 OCR 质量对要素核对的影响。
- 多 Agent 并行写入 `review.json` 的冲突控制（当前设计为单写者，未做并发测试）。
- 与院内 OA/签章系统的对接（本套件不提供该能力）。

## 复现方式

```bash
git clone <本仓库> && cd iccad-review-skill
python scripts/validate_skills.py
python skills/iccad-review/scripts/self_check.py
```

期望末行输出 `OK skills=1 catalog=1 problems=0` 与 `30/30 checks passed`。
