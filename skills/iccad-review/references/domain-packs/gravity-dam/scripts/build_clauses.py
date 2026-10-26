#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建混凝土重力坝工程报告审查自带条文库 (references/gd_clauses.json)。

【双数据源 —— 本族唯一】
    ① **SL 319-2018 精编**：读 references/gd_clauses_src.txt。
       块库里的 SL 319 是 **2005 版全文**（876 块），而现行版为 SL 319-2018，
       两版条号不等价（4.x 整体后移、6.3.2/6.3.3 互换、7.4 前移一位、
       新增第 9 章）。用 2005 正文配 2018 条号会出实质错误，故主规范走原文精编。
    ② **18 部配套规范**：从本机 hydro_reviewer 块库 chunks.pkl 按 doc_name 精确提取。

【何时用】
    规范更新、或收录范围调整后重建一次。日常审查**不需要**跑它 ——
    spec_lookup.py 默认直接读本脚本产出的 JSON。

【依赖】
    重建 ① 无依赖；重建 ② 需本机块库与 hydro_reviewer 源码树（pickle 反序列化）。
    换机器若只要主规范，可加 --no-block 跳过块库部分。

【用法】
    python build_clauses.py
    python build_clauses.py --no-block                 # 只建 SL 319-2018 精编
    python build_clauses.py --pkl <chunks.pkl> --src <源码根[,源码根2]> --out <输出.json>
    python build_clauses.py --list                     # 只打印统计，不写文件

【输出】
    references/gd_clauses.json —— 零依赖数据文件，保留块库原顺序（不重排）。
"""
import argparse
import json
import os
import pickle
import re
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— CONFIG（本机专属路径；换机器改这里或用命令行参数）——
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"
DEFAULT_SRC = [
    r"D:\重构文件v9.4\hydro_reviewer",
    r"F:\报告审查\重构文件v9.1.54\hydro_reviewer",
]

# —— 主规范（精编源）——
SPEC_CODE = "SL 319"
SPEC_NAME = "混凝土重力坝设计规范"
SPEC_FULL = "SL 319-2018"

# —— 块库收录的配套规范清单（doc_name 归一化后精确匹配）——
#    主规范 SL 319 **不在此列**：块库版本为 2005 版，已废止，见文件头说明。
SPECS = [
    ("SL 252", "水利水电工程等级划分及洪水标准"),
    ("GB 50201", "防洪标准"),
    ("", "水利工程建设标准强制性条文"),
    ("SL 744", "水工建筑物荷载设计规范"),
    ("SL/T 191", "水工混凝土结构设计规范"),
    ("GB 50007", "建筑地基基础设计规范"),
    ("GB 50021", "岩土工程勘察规范"),
    ("GB 51247", "水工建筑物抗震设计标准"),
    ("SL/T 792", "水工建筑物地基处理设计规范"),
    ("SL 677", "水工混凝土施工规范"),
    ("SL/T 654", "水利水电工程合理使用年限及耐久性设计规范"),
    ("SL 258", "水库大坝安全评价导则"),
    ("SL/T 877", "水库大坝除险加固设计导则"),
    ("SL 303", "水利水电工程施工组织设计规范"),
    ("SL 104", "水利工程水利计算规范"),
    ("SL/T 618", "水利水电工程可行性研究报告编制规程"),
    ("SL/T 619", "水利水电工程初步设计报告编制规程"),
    ("SL/T 386", "水利水电工程边坡与挡土墙设计规范"),
]

# 块字段（缺哪个留空）
FIELDS = ("std_code", "doc_name", "source_spec", "chapter", "section",
          "clause", "level", "layer", "domain", "text", "section_text", "table_text")

# 噪声行（PDF 水印/页脚混入条文）
NOISE = ("网易", "service.netease", "SHUIGONG.COM", "水利工程网")

# 精编源标记：@@ 条号 | 节 | 标题   /   @@TABLE 表号 | 节 | 表名
TAG = re.compile(r"^@@(TABLE)?\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.*)$")


def _norm(s):
    return "".join(str(s or "").split()).upper()


def _strength(text):
    """按条文措辞标注判定强度：must / soft / info。

    族内纪律：判定强度由动词定，不由量值词定。
    「应/不应/不得」→ 硬（must）；「宜/可/不宜」→ 提示（soft）。
    注意剔除「相应/响应/适应/供应/对应」等同形词，否则陈述句会被误判为硬性要求。
    """
    if not text:
        return "info"
    t = text
    for w in ("相应", "响应", "适应", "供应", "对应", "应急", "应当"):
        t = t.replace(w, "")
    if any(w in t for w in ("应", "不得", "必须")):
        return "must"
    if any(w in t for w in ("宜", "可")):
        return "soft"
    return "info"


def load_chunks(pkl_path, src_roots):
    """加载块库；先把源码根塞进 sys.path，否则 pickle 反序列化会 ImportError。"""
    if not os.path.isfile(pkl_path):
        raise SystemExit("块库不存在：%s" % pkl_path)
    for root in src_roots:
        for p in (os.path.join(root, "src"), root):
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
    with open(pkl_path, "rb") as f:
        return pickle.load(f)


def is_noise(text):
    return any(k in text for k in NOISE)


def parse_src(src_path):
    """解析 SL 319-2018 精编源 → chunk 列表。"""
    with open(src_path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    chunks, cur = [], None
    for raw in lines:
        line = raw.rstrip()
        if line.startswith("#") and cur is None:
            continue  # 文件头注释
        m = TAG.match(line)
        if m:
            if cur:
                chunks.append(cur)
            is_tbl, a, b, c = bool(m.group(1)), m.group(2).strip(), m.group(3).strip(), m.group(4).strip()
            if is_tbl:
                # 表块的 clause 用**表号**（表4.2.1），不能用所属节号，否则与条文撞号
                cur = {"kind": "table", "clause": a, "section": b,
                       "chapter": b.split(".")[0], "title": c or a, "lines": []}
            else:
                cur = {"kind": "clause", "clause": a, "section": b,
                       "chapter": (b or a).split(".")[0], "title": c, "lines": []}
            continue
        if cur is not None:
            cur["lines"].append(line)
    if cur:
        chunks.append(cur)

    out = []
    for ch in chunks:
        body = "\n".join(ch["lines"]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if not body and ch["kind"] == "clause":
            continue
        if ch["kind"] == "table":
            out.append({
                "std_code": SPEC_CODE, "doc_name": SPEC_NAME, "source_spec": SPEC_FULL,
                "chapter": ch["chapter"], "section": ch["section"], "clause": ch["clause"],
                "level": "table", "layer": "table", "domain": "混凝土重力坝",
                "text": "【%s】\n%s" % (ch["title"], body),
                "section_text": "", "table_text": body,
            })
        else:
            title = ("【%s】" % ch["title"]) if ch["title"] else ""
            text = (title + "\n" + body).strip()
            out.append({
                "std_code": SPEC_CODE, "doc_name": SPEC_NAME, "source_spec": SPEC_FULL,
                "chapter": ch["chapter"], "section": ch["section"], "clause": ch["clause"],
                "level": _strength(body), "layer": "", "domain": "混凝土重力坝",
                "text": text, "section_text": "", "table_text": "",
            })
    return out


def build_block(pkl_path, src_roots):
    """从块库提取配套规范。"""
    chunks = load_chunks(pkl_path, src_roots)
    want = {_norm(name): code for code, name in SPECS}
    kept = []
    for c in chunks:
        name = _norm(getattr(c, "doc_name", ""))
        if name not in want:
            continue
        text = str(getattr(c, "text", "") or "")
        sec = str(getattr(c, "section_text", "") or "")
        tbl = str(getattr(c, "table_text", "") or "")
        if not (text or sec or tbl) or is_noise(text) or is_noise(sec):
            continue
        rec = {k: getattr(c, k, None) for k in FIELDS}
        if not rec.get("std_code"):
            rec["std_code"] = "GB-强条汇编"
        kept.append(rec)
    return kept


def main():
    ap = argparse.ArgumentParser(description="重建混凝土重力坝工程报告审查自带条文库")
    here = os.path.dirname(os.path.abspath(__file__))
    dflt_src = os.path.join(os.path.dirname(here), "references", "gd_clauses_src.txt")
    ap.add_argument("--src-file", default=dflt_src, help="SL 319-2018 精编源文件")
    ap.add_argument("--pkl", default=DEFAULT_PKL, help="块库 chunks.pkl 路径")
    ap.add_argument("--src", default=",".join(DEFAULT_SRC), help="源码根，逗号分隔")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/gd_clauses.json）")
    ap.add_argument("--no-block", action="store_true", help="只建 SL 319-2018 精编，不读块库")
    ap.add_argument("--list", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    if not os.path.isfile(args.src_file):
        raise SystemExit("精编源文件不存在：%s" % args.src_file)

    main_chunks = parse_src(args.src_file)
    if not main_chunks:
        raise SystemExit("精编解析结果 0 块 —— 检查源文件 @@ 标记格式")

    block_chunks = [] if args.no_block else build_block(
        args.pkl, [s for s in args.src.split(",") if s.strip()])
    chunks = main_chunks + block_chunks

    c = Counter(x["level"] for x in chunks)
    if args.list:
        print("主规范  : %s %s" % (SPEC_FULL, SPEC_NAME))
        print("总块数  : %d（主规范 %d + 配套 %d）" % (len(chunks), len(main_chunks), len(block_chunks)))
        print("语气分布: must=%d soft=%d info=%d table=%d"
              % (c.get("must", 0), c.get("soft", 0), c.get("info", 0), c.get("table", 0)))
        print("主规范节分布:")
        secs = Counter(x["section"] for x in main_chunks)
        for s in sorted(secs, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.split(".")]):
            print("   %-8s %d" % (s, secs[s]))
        if block_chunks:
            print("配套规范块数:")
            got = Counter(r["std_code"] for r in block_chunks)
            for code, name in SPECS:
                k = code or "GB-强条汇编"
                print("   %-14s %-44s %6d" % (k, name[:42], got.get(k, 0)))
        return

    out = args.out or os.path.join(os.path.dirname(here), "references", "gd_clauses.json")
    specs = [{"code": SPEC_CODE, "name": SPEC_FULL + " " + SPEC_NAME}]
    specs += [{"code": code or "GB-强条汇编", "name": name} for code, name in SPECS]
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "desc": "混凝土重力坝工程报告审查自带条文库；主规范为 SL 319-2018 精编，配套规范取自块库",
            "specs": specs,
            "count": len(chunks),
            "chunks": chunks,
        }, f, ensure_ascii=False, indent=0)

    print("已写出 %s" % out)
    print("  主规范: %s %s —— %d 条（must=%d soft=%d info=%d table=%d）"
          % (SPEC_FULL, SPEC_NAME, len(main_chunks),
             sum(1 for x in main_chunks if x["level"] == "must"),
             sum(1 for x in main_chunks if x["level"] == "soft"),
             sum(1 for x in main_chunks if x["level"] == "info"),
             sum(1 for x in main_chunks if x["level"] == "table")))
    print("  配套  : %d 块 / %d 部" % (len(block_chunks), len(SPECS)))
    print("  合计  : %d 块，%.1f KB" % (len(chunks), os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
