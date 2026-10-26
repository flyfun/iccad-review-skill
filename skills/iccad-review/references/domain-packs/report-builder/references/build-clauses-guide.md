# 建条文库指引（build_clauses / spec_lookup）

> 目标：把"域相关规范"从本机块库抽成**零依赖**的 `<prefix>_clauses.json`，让 `spec_lookup.py`
> 在任何机器、任何目录都能取条文。

---

## 一、数据源：块库 chunks.pkl

- 路径：`C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl`（**62 部 / 41,833 块**，全库）。
- 反序列化**必须**先把 hydro_reviewer 源码根塞进 `sys.path`，否则 `ImportError`
  （`build_clauses.load_chunks` 已处理；源码根见脚本内 CONFIG）。
- 块对象字段（缺则留空）：
  `std_code / doc_name / source_spec / chapter / section / clause / level / layer / domain / text / section_text / table_text`。

## 二、收录清单 SPECS 怎么写

`SPECS = [(std_code, doc_name), …]` 按**主规范 → 配套 → 强条汇编**排序：

1. **主规范**（`★主规范`）：本域最核心那一部。
2. **配套**：等级/洪水标准、防洪标准、堤防、水力计算、与本域公式/稳定相关的规范。
3. **末项固定** `("", "水利工程建设标准强制性条文")` → `std_code` 记为 `GB-强条汇编`。

> `doc_name` 是**归一化精确匹配**的键（去空白 + 大写）。**先实测**（见下），名字对不上就 0 块。

## 三、建库前先实测两件事

```python
# 1) 域内规范到底在不在库、doc_name 是什么、多少块
import pickle, os, sys
for r in (r"D:\重构文件v9.4\hydro_reviewer", r"F:\报告审查\重构文件v9.1.54\hydro_reviewer"):
    for p in (os.path.join(r,"src"), r):
        if os.path.isdir(p) and p not in sys.path: sys.path.insert(0,p)
chunks = pickle.load(open(r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl","rb"))
from collections import Counter
c = Counter(getattr(x,"doc_name","") for x in chunks)
for name,n in c.most_common():
    if "<关键词>" in name: print(name, n)     # 用域关键词过滤
```

2) **主规范是否在强条汇编内**：`spec_lookup --spec "GB-强条汇编" --q "<主规范号>"`。
   新规范常**晚于**汇编 → 0 命中是正常的，**不等于没有强条约束**（其约束落在引用规范上）。

## 四、建库

```bash
python scripts/build_clauses.py                 # 默认输出 references/<prefix>_clauses.json
python scripts/build_clauses.py --out other.json
```
产出后**必做**：
- `--list-specs` 点数各规范块数 → 回填 `norms.md` §二与 `limits.md` §一。
- 检查 `带条款号` 数量（如洪评 6,439 块中 4,716 带条号）。
- 若某规范块数为 0 → `doc_name` 写错，回第二步改拼写。

## 五、去空白归一化（必须保留）

库内正文多来自 PDF/OCR，中文词常被**拆字加空格**（"阻 水 比"）。`spec_lookup.py` 的
`match_dict` 对 query 与 text **同时**做 `_norm()`（去空白 + 大写）后做包含判定 —— **不要**改回裸 `in`，
否则 `--q 阻水比` 会漏掉最关键的条（洪评 5.2.2 正是这么丢的）。

> ⚠ 归一化只解决**空白**，**不解决同义词**。`--q 桥墩` 不会返回只写"支墩"的条 —— 那是设计边界，不是 bug。

## 六、公式本体是图片怎么办

块库对**图形化公式**只留**符号说明文字**（洪评 SL/T 808 附录 A = 36 张图 / 0 个 OMML）。
- 能在 `tables.md` 里用"符号定义 + 水力学通用式"还原的 → 还原并**标"待核"**。
- 还原不了的 → **不复算**，只核"报告是否给出计算书、参数是否齐全"。

## 七、表格提取（docx）

`extract_docx_tables.py` 从原报告 docx **网格重建**表格（横向 gridSpan 重复填格、
纵向 vMerge continue 取上行同列；**不做相邻去重**）：
```bash
python scripts/extract_docx_tables.py <报告.docx> --keyword 阻水比   # 提取含关键词的表
python scripts/extract_docx_tables.py <报告.docx> --text-only --out text.txt  # 正文段落
```
限值固化 = **原文 docx 表格** 与 **条文库洁净正文** 双源互校；冲突以现行版原文为准。
