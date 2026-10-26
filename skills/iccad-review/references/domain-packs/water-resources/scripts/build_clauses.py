#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建水资源论证报告审查自带条文库 (references/wr_clauses.json)。

【为什么不走块库】
    hydro_reviewer 的块库 chunks.pkl（62 部 / 41,833 块）里**没有任何一部水资源规范** ——
    全部是水工结构、供水工程、水土保持类。若照族内惯例去块库筛"水资源论证"，
    结果必然是 0 块。因此本技能改用**原文精编**路线：
    把已核对到公开发布原文的条文，逐条落进 references/wr_clauses_src.txt，
    再由本脚本解析成与族内同构的 JSON。

【数据来源】
    references/wr_clauses_src.txt —— GB/T 35580-2017《建设项目水资源论证导则》
    条文精编（条号经多源交叉比对；OCR 残缺条已剔除）。

【何时用】
    条文源文件增补/修订后重建一次。日常审查**不需要**跑它，
    spec_lookup.py 默认直接读本脚本产出的 JSON。

【用法】
    python build_clauses.py
    python build_clauses.py --src <源文件> --out <输出.json> --list

【输出】
    references/wr_clauses.json —— 零依赖数据文件，供 scripts/spec_lookup.py 默认读取。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 源文件里只有一部规范；表头固定（若将来加规范，在此登记）
SPEC_CODE = "GB/T 35580"
SPEC_NAME = "建设项目水资源论证导则"
SPEC_FULL = "GB/T 35580-2017"

TAG = re.compile(r"^@@\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$")


def _strength(text):
    """按条文措辞标注判定强度：must / soft / info。

    族内纪律（血泪教训）：判定强度由动词定，不由量值词定。
    「应/不应/不得」→ 硬（must）；「宜/可/不宜」→ 提示（soft）。

    ⚠ 必须先剔除**同形非语气词**，否则「相应/响应/适应/供应」里的「应」会把
    纯陈述句误判成硬性要求（这是本族最容易踩的假阳性）。
    """
    if not text:
        return "info"
    t = text
    for w in ("相应", "对应", "响应", "适应", "供应", "应急", "应用", "因应"):
        t = t.replace(w, "")
    if any(w in t for w in ("应", "不得", "必须")):
        return "must"
    if any(w in t for w in ("宜", "可")):
        return "soft"
    return "info"


def parse(src_path):
    """解析源文件 → chunk 列表。"""
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
            a, b, c = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if a.startswith("TABLE"):
                # @@TABLE 表1 | 5.2 | 水资源论证分类分级指标
                # 表块的 clause 用**表号**（表1），不能用 b（所属节号），否则与条文条号撞号
                label = a.split(None, 1)[1].strip() if " " in a else a
                sec = b
                cur = {"kind": "table", "clause": label, "section": sec,
                       "chapter": sec.split(".")[0], "title": label, "lines": []}
            else:
                chap = b.split(".")[0] if b else ""
                cur = {"kind": "clause", "clause": a, "section": b,
                       "chapter": chap, "title": c, "lines": []}
            continue
        if cur is not None:
            cur["lines"].append(line)
    if cur:
        chunks.append(cur)

    out = []
    for ch in chunks:
        body = "\n".join(ch["lines"]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if ch["kind"] == "table":
            out.append({
                "std_code": SPEC_CODE, "doc_name": SPEC_NAME, "source_spec": SPEC_FULL,
                "chapter": ch["chapter"], "section": ch["section"], "clause": ch["clause"],
                "level": "table", "layer": "table", "domain": "水资源论证",
                "text": "【%s】%s" % (ch["title"], body),
                "section_text": "", "table_text": body,
            })
        else:
            text = ("【%s】\n%s" % (ch["title"], body)).strip() if ch["title"] else body
            out.append({
                "std_code": SPEC_CODE, "doc_name": SPEC_NAME, "source_spec": SPEC_FULL,
                "chapter": ch["chapter"], "section": ch["section"], "clause": ch["clause"],
                "level": _strength(text), "layer": "", "domain": "水资源论证",
                "text": text, "section_text": "", "table_text": "",
            })
    return out


def main():
    ap = argparse.ArgumentParser(description="重建水资源论证报告审查自带条文库")
    here = os.path.dirname(os.path.abspath(__file__))
    dflt_src = os.path.join(os.path.dirname(here), "references", "wr_clauses_src.txt")
    ap.add_argument("--src", default=dflt_src, help="条文精编源文件")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/wr_clauses.json）")
    ap.add_argument("--list", action="store_true", help="只打印统计，不写文件")
    args = ap.parse_args()

    if not os.path.isfile(args.src):
        raise SystemExit("源文件不存在：%s" % args.src)

    chunks = parse(args.src)
    if not chunks:
        raise SystemExit("解析结果 0 块 —— 检查源文件 @@ 标记格式")

    c = Counter(x["level"] for x in chunks)
    secs = Counter(x["section"] for x in chunks)
    if args.list:
        print("规范    : %s %s" % (SPEC_FULL, SPEC_NAME))
        print("总块数  : %d" % len(chunks))
        print("语气分布: must=%d soft=%d info=%d table=%d"
              % (c.get("must", 0), c.get("soft", 0), c.get("info", 0), c.get("table", 0)))
        print("节分布  :")
        for s in sorted(secs, key=lambda x: [int(p) if p.isdigit() else 0 for p in x.split(".")]):
            print("   %-8s %d" % (s, secs[s]))
        return

    out = args.out or os.path.join(os.path.dirname(here), "references", "wr_clauses.json")
    data = {
        "desc": "GB/T 35580-2017 精编条文库（块库无水资源规范，故按原文精编）",
        "specs": [{"code": SPEC_CODE, "name": SPEC_NAME}],
        "count": len(chunks),
        "chunks": chunks,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("已写出 %s" % out)
    print("  规范  : %s %s" % (SPEC_FULL, SPEC_NAME))
    print("  块数  : %d（must=%d soft=%d info=%d table=%d）"
          % (len(chunks), c.get("must", 0), c.get("soft", 0), c.get("info", 0), c.get("table", 0)))
    print("  体积  : %.1f KB" % (os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main()
