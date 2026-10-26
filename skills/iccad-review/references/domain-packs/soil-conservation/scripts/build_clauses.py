#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建水土保持审查自带条文库 (references/swc_clauses.json)。

【数据来源（两路合并）】
  ① 本机 hydro_reviewer 块库 chunks.pkl —— 取其中属水土保持的 5 部 + 强条汇编；
  ② 库外原件直接解析 —— 块库**未收录**的核心标准，从原始 docx / pdf 解析：
       GB 50433-2018   生产建设项目水土保持技术标准      （桌面 PDF，可抽文本）
       GB/T 50434-2018 生产建设项目水土流失防治标准      （本机 docx）

【排除的源（重要）】
    GB/T 22490-2025 验收规程本机只有一份**低质 txt**（PDF→txt 时小数点丢失，
    如 5.1.3 被抽成 "513"），**入库会产生错误条号**，故不并入；查它须回原件。

【何时用】
    规范库更新后、或本技能收录范围调整后，重建一次即可。
    日常审查**不需要**跑它——spec_lookup.py 默认直接读本脚本产出的 JSON。

【依赖】
    ① pkl 路：需本机 hydro_reviewer 源码树（pickle 反序列化用）；
    ② 库外路：docx 用标准库解析；**pdf 需 pypdf**（缺失时自动跳过 PDF 源并告警）。
    下方 CONFIG 路径是本机专属，换机器须改或走命令行参数。

【用法】
    python build_clauses.py
    python build_clauses.py --pkl <chunks.pkl> --src <源码根[,源码根2]> --out <输出.json>
    python build_clauses.py --no-external        # 只用块库，忽略库外原件

【输出】
    references/swc_clauses.json —— 零依赖数据文件，供 scripts/spec_lookup.py 默认读取。
"""
import argparse
import json
import os
import pickle
import re
import sys

# —— CONFIG（本机专属路径；换机器改这里或用命令行参数）——
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"
DEFAULT_SRC = [
    r"D:\重构文件v9.4\hydro_reviewer",
    r"F:\报告审查\重构文件v9.1.54\hydro_reviewer",
]

# —— 块库收录的规范清单（doc_name 归一化后精确匹配）——
SPECS = [
    ("GB 51018", "水土保持工程设计规范"),
    ("SL 575", "水利水电工程水土保持技术规范"),
    ("SL/T 277", "水土保持监测技术规程"),
    ("SL/T 879", "河湖岸坡生态治理技术规范"),
    ("SL 190", "土壤侵蚀分类分级标准"),
    ("", "水利工程建设标准强制性条文"),
]

# —— 库外原件（块库未收录；直接解析并入）——
#    (std_code, doc_name, path, kind)   kind ∈ {docx, pdf, txt}
#    注：GB/T 22490-2025 未纳入 —— 本机仅有一份小数点丢失的低质 txt（5.1.3→"513"），
#        入库会产出错误条号，故查验收规程须回原件（见 references/norms.md §三）。
EXTERNAL = [
    ("GB 50433", "生产建设项目水土保持技术标准 GB 50433-2018",
     r"C:\Users\Administrator\Desktop\GB 50433-2018 生产建设项目水土保持技术标准.pdf", "pdf"),
    ("GB/T 50434", "生产建设项目水土流失防治标准 GB/T 50434-2018",
     r"C:\Users\Administrator\水利审查工具\specs_db\specs\00-14 生产建设项目水土流失防治标准 GBT50434-2018.docx", "docx"),
]

# 块字段（缺哪个留空）
FIELDS = ("std_code", "doc_name", "source_spec", "chapter", "section",
          "clause", "level", "layer", "domain", "text", "section_text", "table_text")

# 噪声行（PDF 水印/页脚混入条文）
NOISE = ("网易", "service.netease", "SHUIGONG.COM", "水利工程网")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# 条款号行：3.1.1 / 4.7.6 / 5.10.1 / A.0.1 …
CLAUSE_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3}|[A-E]\.\d{1,2}(?:\.\d{1,2}){0,2})\s+(\S.*)$")
APPENDIX_RE = re.compile(r"^附录\s*([A-Ea-e])")
ZONE_RE = re.compile(r"^\s*(条\s*文\s*说\s*明|本规范用词说明|本规范用词用语说明|引用标准名录|前\s*言|目\s*次|公\s*告|制\s*定\s*说\s*明)\s*$")
# 正文起点：第 1 章"总则"或首条 1.0.1 —— 之前是公告/前言/目次，一律丢弃
BODY_START_RE = re.compile(r"^\s*1\s*总\s*则\s*$|^\s*1\.0\.1\s")
# 页眉/页脚/目录点线/纯页码
PAGE_NOISE_RE = re.compile(r"^[·\-\s]*\d{1,3}[·\-\s]*$|^GB(/T)?\s*\d{5}(—|-)?\d{0,4}$|\.{5,}|…{2,}")


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


def read_lines(path, kind):
    """把 docx / pdf / txt 读成行列表（保持文档顺序）。"""
    if kind == "txt":
        return open(path, encoding="utf-8", errors="replace").read().splitlines()
    if kind == "docx":
        import zipfile
        from xml.etree import ElementTree as ET
        root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
        body = root.find(W + "body")
        out = []
        for el in body:
            if el.tag == W + "p":
                out.append("".join(x.text or "" for x in el.iter(W + "t")))
            elif el.tag == W + "tbl":
                for tr in el.findall(W + "tr"):
                    cells = ["".join(x.text or "" for x in tc.iter(W + "t")).strip()
                             for tc in tr.findall(W + "tc")]
                    out.append(" | ".join(cells))
        return out
    if kind == "pdf":
        from pypdf import PdfReader          # 缺失时由调用方捕获
        out = []
        for pg in PdfReader(path).pages:
            out.extend((pg.extract_text() or "").splitlines())
        return out
    raise ValueError("未知来源类型：%s" % kind)


def split_clauses(lines, std_code, doc_name):
    """先定位正文起点丢弃公告/前言/目次，再按条款号切块；跟踪条文说明/附录分区。"""
    text = "\n".join(lines)
    # 归一化被排版空格拆开的条款号："3. 1. 1" → "3.1.1"（仅动数字之间的点）
    text = re.sub(r"(?<=\d)\s*\.\s*(?=\d)", ".", text)
    # 修正 PDF 把 0 误排成字母 O 的条款号："1. O. 2" → "1.0.2"
    text = re.sub(r"(?<=\d)\s*\.\s*[Oo]\s*\.\s*(?=\d)", ".0.", text)
    raw_lines = text.split("\n")

    # 正文起点：跳过前置公告/前言/目录
    start = 0
    for i, ln in enumerate(raw_lines):
        if BODY_START_RE.match(ln.strip()):
            start = i
            break
    raw_lines = raw_lines[start:]

    out = []
    cur = None
    zone = ""
    for raw in raw_lines:
        ln = raw.strip()
        if not ln or PAGE_NOISE_RE.search(ln):
            continue
        if any(k in ln for k in NOISE):
            continue
        if ZONE_RE.match(ln):
            zone = re.sub(r"\s+", "", ln)
            if cur and cur["text"].strip():
                out.append(cur)
                cur = None
            continue
        ma = APPENDIX_RE.match(ln)
        if ma:
            if cur and cur["text"].strip():
                out.append(cur)
                cur = None
            zone = "附录" + ma.group(1)
            continue
        m = CLAUSE_RE.match(ln)
        if m:
            if cur and cur["text"].strip():
                out.append(cur)
            cur = {"clause": m.group(1), "text": m.group(2).strip(), "section": zone}
        elif cur is not None:
            cur["text"] += " " + ln
    if cur and cur["text"].strip():
        out.append(cur)

    DROP_ZONE = {"目次", "前言", "公告", "引用标准名录", "制定说明"}
    recs = []
    for c in out:
        if c["section"] in DROP_ZONE:          # 前置页残块，丢弃
            continue
        t = re.sub(r"\s+", " ", c["text"]).strip()
        if len(t) < 4:
            continue
        recs.append({
            "std_code": std_code, "doc_name": doc_name, "source_spec": doc_name,
            "chapter": "", "section": c["section"], "clause": c["clause"],
            "level": "", "layer": "", "domain": "",
            "text": t[:1200], "section_text": "", "table_text": "",
        })
    return recs


def build_external():
    recs = []
    for code, name, path, kind in EXTERNAL:
        if not os.path.isfile(path):
            print("  [跳过] 原件不存在：%s" % path)
            continue
        try:
            lines = read_lines(path, kind)
        except ImportError as e:
            print("  [跳过] %s 解析缺依赖（%s）—— %s" % (name, e, "pip install pypdf" if kind == "pdf" else ""))
            continue
        except Exception as e:
            print("  [跳过] %s 解析失败：%s" % (name, e))
            continue
        part = split_clauses(lines, code, name)
        print("  [并入] %-42s %5d 条（%s）" % (name, len(part), kind))
        recs.extend(part)
    return recs


def main():
    ap = argparse.ArgumentParser(description="重建水土保持审查自带条文库")
    ap.add_argument("--pkl", default=DEFAULT_PKL, help="块库 chunks.pkl 路径")
    ap.add_argument("--src", default=",".join(DEFAULT_SRC), help="源码根，逗号分隔")
    ap.add_argument("--out", default=None, help="输出 JSON（默认 references/swc_clauses.json）")
    ap.add_argument("--no-external", action="store_true", help="只用块库，忽略库外原件")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "references", "swc_clauses.json")

    # ① 块库路
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
    print("块库路：%d 块" % len(kept))

    # ② 库外原件路
    extra = []
    if not args.no_external:
        print("库外原件路：")
        extra = build_external()
    allrecs = kept + extra

    specs = [{"code": c, "name": n} for c, n in SPECS]
    for code, name, _p, _k in EXTERNAL:
        if any(r["std_code"] == code for r in extra):
            specs.append({"code": code, "name": name})

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "desc": "水土保持工程报告审查自带条文库（重建于 build_clauses.py）",
            "specs": specs,
            "count": len(allrecs),
            "chunks": allrecs,
        }, f, ensure_ascii=False, indent=0)

    from collections import Counter
    print()
    print("saved -> %s" % out)
    print("合计 %d 块 / %d 部" % (len(allrecs), len({r["std_code"] for r in allrecs})))
    for code, n in Counter(r["std_code"] for r in allrecs).most_common():
        print("   %-12s %6d" % (code, n))
    print("带条款号: %d" % sum(1 for r in allrecs if str(r.get("clause") or "").strip()))


if __name__ == "__main__":
    main()
