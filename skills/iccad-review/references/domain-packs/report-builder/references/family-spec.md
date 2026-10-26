# 报告审查技能族 —— 同构约束与命名规约

> 本册是"新技能必须长什么样"的唯一权威源。**结构由脚手架保证，域内容由人填。**
> 现有成员（2026-10）：`earth-dam` / `sluice` / `soil-conservation` / `river-channel` / `flood-impact-report-review`。

---

## 一、目录树（硬约束）

```
<name>-report-review/
  SKILL.md                     ← L2 入口，四步流程 + ▶载入 + 分册索引；正文 <5,000 字符
  skill-meta.yaml              ← applicable_types / trigger_keywords / exclude_domains
  references/
    checklist.md               ← 分块检查项（判定标准 + 失败模式）+ 跨专业一致性
    norms.md                   ← 规范清单 / 取条文方法 / 引用纪律 / 易踩的坑
    compulsory-clauses.md      ← 强制性条文清单
    error-patterns.md          ← 错情模式（★/●/○）
    limits.md                  ← 边界与已知局限
    <prefix>_tables.md         ← 固化限值表（数值判据的固化源）
    <prefix>_works_tables.md   ← 规范章节结构 + 关键构造
    <prefix>_clauses.json      ← 自带条文库（零依赖，build_clauses 产出）
    [numeric-checks.md]        ← 可选：数值项 × 依据 × 限值 × 复算器 覆盖矩阵
  scripts/
    spec_lookup.py             ← 标准件：取条文（去空白归一化 + stderr 诊断 + --quiet）
    extract_docx_tables.py     ← 标准件：docx 表格网格重建
    build_clauses.py           ← 重建自带 JSON（SPECS 内嵌）
    deliver.py                 ← 标准件：交付三关流水线
    calc_*.py                  ← 复算器（每域 3~9 个）
```

**前缀 `prefix`**：技能名去 `-report-review` 后各段首字母（`river-channel` → `rc`，`flood-impact` → `fi`，`soil-conservation` → `sc`）。
`<prefix>_clauses.json` / `<prefix>_tables.md` / `<prefix>_works_tables.md` 三处必须同名同前缀。

---

## 二、五个"不许"

| # | 约束 | 为什么 |
|---|---|---|
| 1 | SKILL.md **正文 <5,000 字符**（frontmatter 不计） | L2 常驻上下文预算；超了会被截断 |
| 2 | 分册索引表 **必须逐册列全**（含 scripts） | 否则"渐进披露"断链，模型找不到分册 |
| 3 | 每一步末尾 **必须有 ▶ 载入** 锚点 | 决定何时翻哪册；缺失=该步无判据 |
| 4 | 判据必须 **落到"规范号 + 条号/表号 + 数值"** | 无依据的判词=假结论；限值不许硬编码在 SKILL.md |
| 5 | 复算器统一 **退出码语义**（0/1/2/3）+ **三方比对** | 便于批处理与自检；见 `calc-conventions.md` |

---

## 三、命名规约

- **技能名**：`<域>-report-review`，小写连字符（`pump-station-report-review`）。
- **主规范字段**：`<prefix>_clauses.json` 用 `--list-specs` 实测块数回填 `norms.md` §二与 `limits.md` §一。
- **强条汇编**：`SPECS` 末项固定 `("", "水利工程建设标准强制性条文")`，入库后 `std_code` 记为 `GB-强条汇编`。
- **`level=mandatory` ≠ 强条**：那是"含'应'字"的入库启发式标记，**不可**据此写"违反强制性条文"。

---

## 四、五部成员的差异化参数（照抄时对照）

| 技能 | 前缀 | 主规范 | 块数 | 复算器数 | 强条锚点 |
|---|---|---|---|---|---|
| earth-dam | dam | SL 274 | 13,480 | 2 | 见该技能 |
| sluice | sluice | SL 265 | 9,766 | 4 | SL 265 4.2.4/4.2.5/7.3.13/7.3.14 |
| soil-conservation | swc | GB 51018 | 4,013 | 4 | GB 50433 3.2.3/3.2.5 等 11 条 |
| river-channel | rc | GB 50707 + GB 50286 | 5,808 | 4 | GB 50707 4.1.3、GB 50286 7.2.4/7.2.5/10.1.3 |
| flood-impact | flood | SL/T 808 | 6,439 | 9 | GB 50286 10.1.3、GB 50201 11.8.3★ |

> **同一条款在多部技能里出现时，限值必须逐值对齐**（如 GB 50286 表 3.2.5 挡墙抗滑在本族多处引用）。
