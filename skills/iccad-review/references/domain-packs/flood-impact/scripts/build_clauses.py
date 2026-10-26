#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建洪评审查自带条文库 (references/flood_clauses.json)。

【数据来源】
    本机 hydro_reviewer 块库 chunks.pkl —— 取其中属"洪水影响评价 / 防洪标准 /
    工程等级 / 堤防 / 河道整治 / 水利计算 / 治涝 / 岸线 / 边坡挡墙"及其配套的
    规范，共 16 部（清单见下方 SPECS），生成本技能自带的零依赖条文 JSON。

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
    references/flood_clauses.json —— 零依赖数据文件，供 scripts/spec_lookup.py 默认读取。
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
    ("SL/T 808", "洪水影响评价技术导则"),               # ★主规范（技术要求/分析计算/两类评价/附录A算法）
    ("GB 50201", "防洪标准"),                          # 防护等级 → 防洪标准（各类防护对象）
    ("SL 252", "水利水电工程等级划分及洪水标准"),        # 工程等别 / 水工建筑物级别 / 堤防级别
    ("GB 50286", "堤防工程设计规范"),                   # 堤防级别/稳定/交叉建筑物 ★强条 10.1.3
    ("GB 50707", "河道整治设计规范"),                   # 治导线 / 河道演变 / 防护工程（冲刷公式源）
    ("GB 50265", "泵站设计标准"),                       # A.6 灌排影响（泵站扬程/取排水能力）
    ("SL 265", "水闸设计规范"),                         # A.6 灌排影响（水闸灌排能力/防渗/稳定）
    ("SL 279", "水工隧洞设计规范"),                     # 穿河穿堤隧洞
    ("SL/T 171", "堤防工程管理设计规范"),                # 管理范围 / 保护范围 / 防汛交通
    ("SL 104", "水利工程水利计算规范"),                  # 水面线 / 水力计算
    ("SL 723", "治涝标准"),                             # 治涝设计标准
    ("SL/T 826", "河湖岸线保护和利用规划编制规程"),        # 岸线控制线 / 功能分区（规划符合性）
    ("SL/T 852", "河湖管理范围划定技术规范"),             # 河湖管理范围（工程位置是否涉河）
    ("SL/T 879", "河湖岸坡生态治理技术规范"),             # 岸坡生态防护（临河项目）
    ("SL/T 386", "水利水电工程边坡与挡土墙设计规范"),      # 岸坡/挡墙稳定安全系数
    ("", "水利工程建设标准强制性条文"),                   # 强条汇编（判"违反强制条文"必查）
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
    ap = argparse.ArgumentParser(description="重建洪评审查自带条文库")
    ap.add_argument("--pkl", default=DEFAULT_PKL, help="块库 chunks.pkl 路径")
    ap.add_argument("--src", default=",".join(DEFAULT_SRC), help="源码根，逗号分隔")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/flood_clauses.json）")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "references", "flood_clauses.json")

    chunks = load_chunks(args.pkl, [s for s in args.src.split(",") if s.strip()])
    want = {_norm(name): code for code, name in SPECS}
    kept = []
    missing = set(want) - set()
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
            "desc": "洪水影响评价报告审查自带条文库（重建于 build_clauses.py）",
            "specs": specs,
            "count": len(kept),
            "chunks": kept,
        }, f, ensure_ascii=False, indent=0)

    got = Counter(r["std_code"] for r in kept)
    print("saved -> %s" % out)
    print("合计 %d 块 / %d 部" % (len(kept), len(got)))
    for c, n in SPECS:
        code = c or "GB-强条汇编"
        print("   %-14s %-44s %6d" % (code, n[:42], got.get(code, 0)))
    print("带条款号: %d" % sum(1 for r in kept if str(r.get("clause") or "").strip()))


if __name__ == "__main__":
    main()
