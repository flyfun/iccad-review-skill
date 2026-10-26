<!--
本文件由 scripts/sync_domain_packs.py 从 SLReview_Py 引擎仓复制生成，不要手工修改。
源文件：skills/hydro-report-review-builder/SKILL.md
引擎版本：v26.0.0
同步时间：2026-10-26 15:14
口径以引擎仓为准；重跑同步脚本即可覆盖。
-->

# 报告审查技能构建器

## 这个 Skill 是什么

**脚手架 + 规约**，不是域知识卡。回答：要新建一部"XX报告审查"技能时，**怎么起、按什么结构、
哪些必须一致、域内容填哪、怎么交付**。族内已有土石坝 / 水闸 / 水保 / 河道 / 洪评五部同构技能，
本技能把它们的**共同骨架**固化，使新技能"长得一样、判据同样可追"。

## 何时用 / 不适用

- **用**：要**新建**一部报告审查技能（新域），或要把族内某部技能的结构对齐。
- **不用**：审查某份具体报告（走对应域技能）；只改现有技能的域内容（直接编辑该技能）。

## 构建总流程

```
新域需求
 ├─[0] 定域 ── 域卡片：技能名/域/主规范/收录规范清单/复算器清单/跨校验数
 ├─[1] 起骨架 ── skeleton.py 渲染模板 → 目录树 + 标准件脚本
 ├─[2] 建条文库 ── 实测 doc_name → build_clauses.py → <prefix>_clauses.json
 ├─[3] 写分册 ── 逐册填 TODO（判定标准落到 规则号+表号+数值）
 ├─[4] 写复算器 ── 按 calc_script.py.tmpl（判据方向纪律 + 退出码 + 三方比对）
 └─[5] 交付三关 ── deliver.py：编译/字数/残留/validate → 打包 → 同步 → md5
```

**每一步该翻哪一册，见该步末尾的 ▶ 载入。**

---

## 第 0 步：定域（先写域卡片）

用一段 JSON 描述这个域，其余由脚手架推导。**必填**：`name / title / domain / main_spec / main_spec_name`；
**常用**：`specs`（收录规范清单 `[[代码,全名],…]`）、`calc`（复算器 `[[文件名,说明],…]`）、
`triggers / exclude`、`block_count / cross_pairs / error_count`。

> 关键判定：**主规范是哪一部**；**分几块**（跟主规范章节走，族内惯例 12 块）；
> **定几个复算器**（本域最容易被报告写错的数值，每个一个脚本）。

---

## 第 1 步：起骨架

```bash
python scripts/skeleton.py --card domain-card.json --out "C:\Users\Administrator\Desktop\自建skill"
```

产出 `SKILL.md`、`skill-meta.yaml`、7 册 references（带 TODO）、`scripts/`（含标准件
`spec_lookup.py` / `extract_docx_tables.py` / `deliver.py` + 由 SPECS 渲染的 `build_clauses.py`
+ 按清单渲染的 `calc_*.py`），并**打印待办清单与 TODO 计数**。

> ▶ **载入**：`references/family-spec.md`（目录树 + 五个"不许" + 命名规约 + 五部成员参数对照）。

---

## 第 2 步：建条文库

先在块库里**实测** `doc_name` 与块数（名字对不上就是 0 块），再跑建库：

```bash
python scripts/build_clauses.py && python scripts/spec_lookup.py --list-specs
```

回填 `norms.md` §二、`limits.md` §一 的块数（**以实测为准**）。

> ▶ **载入**：`references/build-clauses-guide.md`（块库字段 / SPECS 写法 / 去空白归一化 / 图片公式处置）。

---

## 第 3 步：写分册

逐册清掉 TODO。**判定标准必须落到"规范号 + 条号/表号 + 具体数值或判词"**；
`norms.md` 的引用纪律与易踩的坑是**该册的权威定义**，入口不重复。

> ▶ **载入**：`references/family-spec.md` §二（五个"不许"：正文字数 / 分册索引 / ▶载入 / 判据可追 / 退出码统一）。

---

## 第 4 步：写复算器

按 `templates/calc_script.py.tmpl` 实现。**核心是判据方向**：下限型用 `_check_min`、
上限型用 `_check_max`、区间型取**下限**作要求；"应/不应"进 `bad`（rc=1），"宜"只出 ▲ 提示。

> ▶ **载入**：`references/calc-conventions.md`（退出码 0/1/2/3 + 判据方向 + 三方比对 + 容差）。

---

## 第 5 步：交付三关

```bash
python scripts/deliver.py --name <name> --check      # 体检
python scripts/deliver.py --name <name> --deliver    # 打包+同步+md5
# 再到安装目录跑一次 --list-specs，证明零依赖可独立运行
```

> ▶ **载入**：`references/delivery-checklist.md`（三关细节 + 安装副本自检 + 返工原因）。

---

## 避坑（硬规则）

**动手前先读** `references/pitfalls.md` —— 唯一权威定义，本入口不重复。
**最要紧三条**：① **同一文件多处 Edit 禁止并行**（会静默覆盖）；② `package_skill` 输出落点是 **cwd**
（打包须从源根跑，否则 zip 自我包含）；③ **`level=mandatory` ≠ 强制性条文**。

## 边界

- 本技能只保证**结构同构与交付规范**；**域判据的正确性由人负责**（须查现行规范原文）。
- 产出为**审查技能骨架**，非审批结论；新技能的判据须**逐条落实现行有效规范**。

## 分册索引

| 文件 | 内容 |
|---|---|
| `references/family-spec.md` | **目录树 + 五个"不许" + 命名规约** + 五部成员参数对照 |
| `references/build-clauses-guide.md` | 块库字段、SPECS 写法、去空白归一化、图片公式处置 |
| `references/calc-conventions.md` | **退出码统一语义 + 判据方向纪律 + 三方比对** |
| `references/delivery-checklist.md` | 交付三关、安装副本自检、常见返工原因 |
| `references/pitfalls.md` | **建技能踩过的坑 15 条**（工具/检索/写作/记忆） |
| `templates/`（11 个：SKILL.md.tmpl 等） | 各文件模板（骨架渲染用，唯一含待填标记处） |
| `scripts/skeleton.py` | **一键起骨架**（读域卡片 → 渲染模板 → 目录树 + 待办） |
| `templates/build_clauses.py.tmpl` | 渲染成新技能的建库脚本（SPECS 内嵌，家族同构） |
| `scripts/spec_lookup.py` | 标准件：取条文（去空白归一化 + stderr 诊断 + --quiet） |
| `scripts/extract_docx_tables.py` | 标准件：docx 表格网格重建 |
| `scripts/deliver.py` | **交付流水线**（体检 + 打包 + 同步 + md5） |
