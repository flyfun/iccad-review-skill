#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建河道审查自带条文库 (references/rc_clauses.json)。

【数据来源】
    本机 hydro_reviewer 块库 chunks.pkl —— 取其中属"河道 / 堤防 / 防洪 / 疏浚 / 治涝"
    及其配套的规范，共 15 部（清单见下方 SPECS），生成本技能自带的零依赖条文 JSON。

【何时用】
    规范库更新后、或本技能收录范围调整后，重建一次即可。
    日常审查**不需要**跑它 —— spec_lookup.py 默认直接读本脚本产出的 JSON。

【依赖】
    需本机 hydro_reviewer 源码树（pickle 反序列化用）。下方 CONFIG 路径为本机专属，
    换机器须改或走命令行参数。

【用法】
    python build_clauses.py
    python build_clauses.py --pkl <chunks.pkl> --src <源码根[,源码根2]> --out <输出.json>

【输出】
    references/rc_clauses.json —— 零依赖数据文件，供 scripts/spec_lookup.py 默认读取。
"""
import argparse
import json
import os
import pickle
import sys
from collections import Counter

# —— CONFIG（本机专属路径；换机器改这里或用命令行参数）——
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"
DEFAULT_SRC = [
    r"D:\重构文件v9.4\hydro_reviewer",
    r"F:\报告审查\重构文件v9.1.54\hydro_reviewer",
]

# —— 块库收录的规范清单（doc_name 归一化后精确匹配）——
#    (std_code, doc_name)
SPECS = [
    ("GB 50707", "河道整治设计规范"),                 # 主规范（整治原则/治导线/防护工程）
    ("GB 50286", "堤防工程设计规范"),                 # 主规范（堤防级别/断面/稳定/交叉建筑物）
    ("SL 252", "水利水电工程等级划分及洪水标准"),      # 工程等别 / 建筑物级别 / 洪水标准
    ("GB 50201", "防洪标准"),                         # 防护等级 → 防洪标准
    ("SL 17", "疏浚与吹填工程技术规范"),               # 清淤疏浚 断面/坡比/超深超宽
    ("SL 723", "治涝标准"),                           # 治涝设计标准
    ("SL/T 260", "堤防工程施工规范"),                  # 堤防施工
    ("SL/T 171", "堤防工程管理设计规范"),              # 管理范围 / 保护范围
    ("SL/T 826", "河湖岸线保护和利用规划编制规程"),      # 岸线控制线 / 功能分区
    ("SL/T 879", "河湖岸坡生态治理技术规范"),           # 岸坡生态防护 / 生态护坡
    ("SL/T 386", "水利水电工程边坡与挡土墙设计规范"),    # 护岸挡墙 级别 / 稳定安全系数
    ("SL/T 852", "河湖管理范围划定技术规范"),           # 河湖管理范围
    ("SL 104", "水利工程水利计算规范"),                 # 水面线 / 水力计算
    ("SL/T 808", "洪水影响评价技术导则"),               # 涉河建设项目 洪水影响评价
    ("", "水利工程建设标准强制性条文"),                 # 强条汇编（判"违反强制条文"必查）
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
    ap = argparse.ArgumentParser(description="重建河道审查自带条文库")
    ap.add_argument("--pkl", default=DEFAULT_PKL, help="块库 chunks.pkl 路径")
    ap.add_argument("--src", default=",".join(DEFAULT_SRC), help="源码根，逗号分隔")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/rc_clauses.json）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "references", "rc_clauses.json")

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
        if not (text or sec or tbl) or is_noise(text) or is_noise(sec):
            continue
        rec = {k: getattr(c, k, None) for k in FIELDS}
        if not rec.get("std_code"):
            rec["std_code"] = "GB-强条汇编"
        kept.append(rec)

    specs = [{"code": c, "name": n} for c, n in SPECS]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "desc": "河道工程报告审查自带条文库（重建于 build_clauses.py）",
            "specs": specs,
            "count": len(kept),
            "chunks": kept,
        }, f, ensure_ascii=False, indent=0)

    print("saved -> %s" % out)
    print("合计 %d 块 / %d 部" % (len(kept), len({r["std_code"] for r in kept})))
    for code, n in Counter(r["std_code"] for r in kept).most_common():
        print("   %-12s %6d" % (code, n))
    print("带条款号: %d" % sum(1 for r in kept if str(r.get("clause") or "").strip()))


if __name__ == "__main__":
    main()
