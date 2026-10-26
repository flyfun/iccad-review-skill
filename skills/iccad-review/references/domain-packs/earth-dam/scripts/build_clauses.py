#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 hydro_reviewer 块库重建土石坝审查自带条文库 (references/dam_clauses.json)。

【何时用】
    规范库更新后、或本技能收录范围调整后，重建一次即可。
    日常审查**不需要**跑它——spec_lookup.py 默认直接读本脚本产出的 JSON。

【依赖】
    本机 hydro_reviewer 源码树（pickle 反序列化用）+ 块库 chunks.pkl。
    下方 CONFIG 里的路径是**本机专属**，换机器须调整或改用命令行参数。

【用法】
    python build_clauses.py
    python build_clauses.py --pkl <chunks.pkl> --src <源码根[,源码根2]> --out <输出.json>

【输出】
    references/dam_clauses.json —— 零依赖数据文件，保留**块库原顺序**（不重排），
    供 scripts/spec_lookup.py 默认读取。
"""
import argparse
import json
import os
import pickle
import sys

# —— CONFIG（本机专属路径；换机器改这里或用命令行参数）——
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"
DEFAULT_SRC = [
    r"D:\重构文件v9.4\hydro_reviewer",
    r"F:\报告审查\重构文件v9.1.54\hydro_reviewer",
]

# —— 本技能收录的规范清单（doc_name 归一化后精确匹配）——
#    改动这里就等于改动"技能自带的条文覆盖范围"。
SPECS = [
    ("SL 274", "碾压式土石坝设计规范"),                      # ★主规范
    ("SL 258", "水库大坝安全评价导则"),                      # 安全评价类报告主依据
    ("SL/T 877", "水库大坝除险加固设计导则"),                 # 除险加固类报告
    ("SL 564", "土坝灌浆技术规范"),                          # 坝体/坝基灌浆防渗
    ("SL 174", "水利水电工程混凝土防渗墙施工技术规范"),        # 防渗墙
    ("SL 252", "水利水电工程等级划分及洪水标准"),              # 工程级别
    ("GB 50201", "防洪标准"),                               # 洪水标准
    ("", "水利工程建设标准强制性条文"),                       # ★判"违反强条"必查
    ("SL 744", "水工建筑物荷载设计规范"),                     # 荷载
    ("GB 50007", "建筑地基基础设计规范"),                     # 地基承载力/沉降
    ("GB 50021", "岩土工程勘察规范"),                         # 地质勘察参数
    ("SL/T 191", "水工混凝土结构设计规范"),                    # 混凝土结构
    ("GB 51247", "水工建筑物抗震设计标准"),                    # 抗震（替代 SL 203）
    ("SL 303", "水利水电工程施工组织设计规范"),                 # 施工导流与度汛
    ("SL/T 386", "水利水电工程边坡与挡土墙设计规范"),            # 边坡稳定
    ("SL/T 619", "水利水电工程初步设计报告编制规程"),            # 报告深度
    ("SL/T 618", "水利水电工程可行性研究报告编制规程"),          # 报告深度
    ("SL/T 654", "水利水电工程合理使用年限及耐久性设计规范"),      # 耐久性
    ("SL 104", "水利工程水利计算规范"),                        # 水文水利计算
]

# 块字段（缺哪个留空）
FIELDS = ("std_code", "doc_name", "source_spec", "chapter", "section",
          "clause", "level", "layer", "domain", "text", "section_text", "table_text")

# 噪声行（PDF 水印/页脚混入条文）
NOISE = ("网易", "service.netease", "SHUIGONG.COM", "水利工程网")


def _norm(s):
    return "".join(str(s or "").split()).upper()


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


def main():
    ap = argparse.ArgumentParser(description="重建土石坝审查自带条文库")
    ap.add_argument("--pkl", default=DEFAULT_PKL, help="块库 chunks.pkl 路径")
    ap.add_argument("--src", default=",".join(DEFAULT_SRC), help="源码根，逗号分隔")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/dam_clauses.json）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "references", "dam_clauses.json")

    chunks = load_chunks(args.pkl, [s for s in args.src.split(",") if s.strip()])
    want = {_norm(name): code for code, name in SPECS}

    kept = []
    for c in chunks:
        name = _norm(getattr(c, "doc_name", ""))
        if name not in want:
            continue
        text = str(getattr(c, "text", "") or "")
        sec = str(getattr(c, "section_text", "") or "")
        tbl = str(getattr(c, "table_text", "") or "")
        if not (text or sec or tbl):
            continue
        if is_noise(text) or is_noise(sec):
            continue
        rec = {k: getattr(c, k, None) for k in FIELDS}
        # 强制条文块的标准号为空，补一个可读标签
        if not rec.get("std_code"):
            rec["std_code"] = "GB-强条汇编"
        kept.append(rec)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "desc": "土石坝工程报告审查自带条文库（重建于 build_clauses.py）",
            "specs": [{"code": c, "name": n} for c, n in SPECS],
            "count": len(kept),
            "chunks": kept,
        }, f, ensure_ascii=False, indent=0)

    # 统计
    from collections import Counter
    cnt = Counter(r["doc_name"] for r in kept)
    print("saved -> %s" % out)
    print("kept  %d chunks / %d specs" % (len(kept), len(cnt)))
    for name, n in cnt.most_common():
        print("   %-46s %6d" % (name, n))
    print("带条款号: %d" % sum(1 for r in kept if str(r.get("clause") or "").strip()))


if __name__ == "__main__":
    main()
