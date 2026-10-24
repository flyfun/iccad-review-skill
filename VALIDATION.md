# 验证记录

## 本次验证范围

**只有合成流程与脚本行为**。没有真实项目盲测，因此不提供检出率、漏报率或节时承诺。
示例中的依据编号（`EX-` 前缀）、数值与人工记录全部虚构。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-24 |
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
```

## 结果

| 检查 | 预期 | 实测 |
|---|---|---|
| 技能目录/元数据/引用一致性 | 17 skills、0 问题 | 通过 |
| 合成自检 `self_check.py` | 12 项全通过 | 12/12 |
| `example-review.json` 结构校验 | 退出码 0 | 0 |
| `example-review.json --gate` | 退出码 3（存在待复核与未闭环） | 3 |
| `example-complete.json --gate` | 退出码 0（闭环齐备） | 0 |
| 篡改哈希 | 被 `--verify-files` 拒绝 | 拒绝 |
| 单位换算不一致 | 被数值复算拒绝 | 拒绝 |
| 计划项被删除 | 计为阻塞而非静默通过 | 阻塞 |
| draft 规则用于已求值检查 | 报结构错误 | 错误 |
| 引擎导入（无引文命中） | 记为 `insufficient_input`，不补造引文 | 符合 |
| 报告渲染 | 七个章节齐全 | 齐全 |

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
9. 渲染结果包含全部必需章节。

## 未验证

- 真实报告上的检出率、误报率、覆盖完整性。
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

期望末行输出 `17 skills ... problems=0` 与 `12/12 checks passed`。
