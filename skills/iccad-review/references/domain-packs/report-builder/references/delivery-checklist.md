# 交付三关与同步（delivery-checklist）

> 家族交付约定：**编译 → 清缓存 → 打包 → 同步 → md5**。`scripts/deliver.py` 已串成一条命令。
> 本册说清每步意图与判据，便于出问题时定位。

---

## 一、体检（--check）

```bash
python scripts/deliver.py --name <name> --check
```
体检项：

| 项 | 判据 | 不过怎么办 |
|---|---|---|
| `py_compile` | scripts/*.py 全编译通过 | 看最后一行报错，修语法 |
| `SKILL.md body < 5000` | **正文**（frontmatter 之外）字符数 | 精简啰嗦句；删重复说明；保留 ▶载入与分册索引 |
| 无 `__pycache__` | 打包前清干净 | `deliver` 会自动清 |
| **骨架待填标记清零** | 无未填占位（TODO 标记，模板目录除外） | 逐处填域内容（判定标准要落到规则号+表号+数值） |
| `quick_validate` | 输出含 "valid" | 多半是 frontmatter 缺 `name`/`description` 或 YAML 缩进坏 |

## 二、交付（--deliver）

```bash
python scripts/deliver.py --name <name> --deliver
```
按序做：

1. **清 `__pycache__`**（否则会被打进 zip）。
2. **打包**：`package_skill.py <name>`，**cwd 固定为源根 `SRC_ROOT`**。
   ⚠ 输出落点是 **cwd** —— cwd 若是技能目录，zip 会写进技能目录里，**下次打包就自我包含**。
   本脚本固定从源根打包，并**主动清理**误落入技能目录的 zip。
3. **同步** `~/.workbuddy/skills/<name>`（`copytree`，忽略 pycache/pyc）。
4. **逐文件 md5 校验**：源根目录 vs 安装目录，**必须全一致**。
5. **嵌套 zip 检查**：zip 内不得再有 `.zip` 条目。

## 三、安装副本独立自检（必做）

同步后，**在安装目录**跑一次，证明"零依赖、与目录无关"：
```bash
cd "C:\Users\Administrator\.workbuddy\skills\<name>"
python scripts/spec_lookup.py --list-specs      # 应回出各规范块数
python scripts/calc_<x>.py --mode <m> ...        # 应能独立算出结果
```

## 四、常见返工原因

| 现象 | 根因 | 处置 |
|---|---|---|
| md5 不一致 | 同步**之后**又改了源文件 | 再跑一次 `--deliver` |
| zip 里套着 zip | cwd 传成了技能目录 | 用 `deliver.py`（已固定 cwd）|
| 安装副本跑不动 | 缺 JSON / 路径写死成绝对 | 检查 DEFAULT_JSON 是**相对脚本定位** |
| 正文超 5000 | 域内容塞进了入口 | 移到分册，入口只留流程与索引 |
| 词条召回 0 | doc_name 写错 / 引旧版 | 回 `build-clauses-guide.md` 第二步实测 |

## 五、记忆与收尾

- 追加当日工作日志到工作区 `.workbuddy/memory/YYYY-MM-DD.md`（append-only）。
- 项目级长期约定写 `.workbuddy/memory/MEMORY.md`（**≤3,000 字符**，超了合并去重）。
- 技能族的"技能总表"（技能 / 域 / 自带库 / 强条 / 复算器）要**同步加一行**。
- 清理临时目录与 `__pycache__`，确认无残留再收口。
