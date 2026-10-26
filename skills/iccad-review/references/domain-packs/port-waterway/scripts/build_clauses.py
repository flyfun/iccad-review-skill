#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建水运工程报告审查自带条文库 (references/pw_clauses.json)。

【数据来源 —— 与族内其余技能不同】
    本域**不使用** chunks.pkl 块库（块库 62 部里没有任何 JTS 水运规范）。
    改从本机 10 部 JTS 规范 **docx 原文**直接解析：
    段落 → 章 / 节 / 条 / 款，`<w:tbl>` → 表格网格，公告区 → 强制性条文清单。

    三种数据源对比：
      · 块库（土石坝/水闸/泵站/河道/洪评/水保/重力坝配套）—— 最省事，但版本可能滞后；
      · 手写精编（水资源论证 / 重力坝主规范）—— 可控，但费时、易漏条；
      · **docx 原文自动解析（本域首创）**—— 条号层级天然规整，强条清单写在公告里，
        解析后可全文自检（条号连续性 + 强条可定位），是三者中最可核的一种。

【强条怎么来的】
    JTS 规范在发布公告与"制定说明"里**逐条列出**强制性条文条号，例如
    JTS 167—2018：「本《规范》第3.1.2.1款、第3.1.5条……为强制性条文，必须严格执行。」
    本脚本从公告区自动抓取条号集合，回填到对应记录的 `mandatory` 字段。
    ⚠ 公告写"某条中的**黑体字部分**为强制性条文"的，docx 转换后黑体标记已丢失
      （实测 `<w:b/>` 全部缺失），因此只能标到**条/款级**，不能标到句级。
      该局限写入 `mandatory_note` 与 references/limits.md，不得据此外推"整条强制"。

【何时用】
    规范版本更新后，把新 docx 放进 DOC_DIR，改 DOCS 清单，重建一次。
    日常审查**不需要**跑它 —— spec_lookup.py 默认直接读本脚本产出的 JSON。

【依赖】
    仅标准库（zipfile + xml.etree）。**不需要源码树、不需要 pickle**。

【用法】
    python build_clauses.py
    python build_clauses.py --doc-dir <目录> --out <输出.json> [--list]

【输出】
    references/pw_clauses.json —— 零依赖数据文件，供 scripts/spec_lookup.py 默认读取。
"""
import argparse
import json
import os
import re
import sys
import zipfile
from collections import Counter, OrderedDict
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# —— CONFIG（本机专属路径；换机器改这里或用命令行参数）——
DEFAULT_DOC_DIR = r"F:\报告审查\_rebuild_test_db\specs"

# 收录清单：(规范号, docx 文件名, 规范全名, 版本全称, 是否主规范)
#   规范号用于检索过滤；文件名必须精确（含全角/空格差异时改这里）。
DOCS = [
    ("JTS 167", "JTS 167-2018 码头结构设计规范.docx", "码头结构设计规范", "JTS 167-2018", True),
    ("JTS 165", "！海港总体设计规范+JTS+165-2025.docx", "海港总体设计规范", "JTS 165-2025", False),
    ("JTS 145", "港口与航道水文规范JTS145-2015（2022版）.docx", "港口与航道水文规范", "JTS 145-2015(2022版)", False),
    ("JTS 144-1", "JTS 144-1-2010 港口工程荷载规范.docx", "港口工程荷载规范", "JTS 144-1-2010", False),
    ("JTS 154", "JTS+154-2018 防波堤与护岸设计规范.docx", "防波堤与护岸设计规范", "JTS 154-2018", False),
    ("JTS 181", "JTS 181-2016 航道工程设计规范.docx", "航道工程设计规范", "JTS 181-2016", False),
    ("JTS 147", "JTS 147-2017 水运工程地基设计规范.docx", "水运工程地基设计规范", "JTS 147-2017", False),
    ("JTS 147-7", "JTS 147-7-2022 水运工程桩基设计规范.docx", "水运工程桩基设计规范", "JTS 147-7-2022", False),
    ("JTS 120-3", "JTS_120-3-2018 临河临湖临海工程航道通航条件影响评价报告编制规定.docx",
     "临河临湖临海工程航道通航条件影响评价报告编制规定", "JTS 120-3-2018", False),
    ("JTS/T 110-4", "！港口工程初步设计文件编制规定+JTS-T+110-4-2025.docx",
     "港口工程初步设计文件编制规定", "JTS/T 110-4-2025", False),
]

# —— 解析正则 ——
RE_SUB = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){3})\s*(\S.*)$")          # 3.1.2.1 款
RE_CLAUSE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){2})\s*(\S.*)$")       # 3.1.2   条
RE_SECTION = re.compile(r"^(\d{1,2}\.\d{1,2})\s*([^\d\s].{0,30})$")   # 3.1     节
RE_CHAPTER = re.compile(r"^(\d{1,2})\s*([^\d\s].{0,28})$")            # 3       章
RE_APPX_SUB = re.compile(r"^([A-Z](?:\.\d{1,2}){2,3})\s*(\S.*)$")      # A.0.1.1 附录款
RE_APPX_CLAUSE = re.compile(r"^([A-Z](?:\.\d{1,2}){1,2})\s*(\S.*)$")   # A.0.1   附录条
RE_TABLE = re.compile(r"^表\s*([A-Z]?\d+(?:\.\d+)*(?:[-—–.]\d+)*(?:\.\d+)?)\s*(.*)$")
# "海船系缆力标准值表10.2.5-1"：表题在前、表号收尾（JTS 144-1 的排版）
RE_TABLE_TAIL = re.compile(r"^(.{2,30}?)表\s*([A-Z]?\d+(?:\.\d+)+(?:[-—–]\d+)?)\s*$")
RE_MAND_HEAD = re.compile(r"(本[《<]?规范[》>]?|本规定).{0,8}第")

# 全角 → 半角（JTS 154 的公告整段是全角数字）
FULL2HALF = {ord(c): ord(c) - 0xFEE0 for c in "０１２３４５６７８９．"} 
FULL2HALF.update({0x3000: 0x20})


def _norm(s):
    """归一化：全角数字转半角、去空白、去掉常见 OCR 噪声。"""
    return re.sub(r"\s+", "", (s or "").translate(FULL2HALF))


def _clean(s):
    """收拢空白，并去掉**汉字与汉字之间**的换行残留空格。

    docx 段落内换行被抽成空格，正文会出现"造成经济损失 以及影响社会"这种断字，
    直接抄进审查意见很难看。只合并"汉字+空格+汉字"，不碰数字/单位/英文，
    故 "1.30~1.40"、"50 m"、"JTS 167" 不受影响。
    """
    s = re.sub(r"[ \t\u3000]+", " ", (s or "")).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", s)


def _split_no(t, groups):
    """从段落**原文**剥离条号，返回 (条号, 剩余文本)；不匹配返回 ("", t)。

    为什么要容忍点两侧空格：JTS 154-2018 与 JTS 144-1-2010 的正文排成
    "3. 1. 4   防波堤与护岸结构的设计使用年限……"，用 `^(\\d+\\.\\d+\\.\\d+)`
    直接匹配会整部漏条（实测 JTS 154 只剩 83 条、JTS 144-1 只剩 67 条）。

    groups=1 章 / 2 节 / 3 条 / 4 款；首字符为大写字母时按附录条号处理。
    """
    if not t:
        return "", t
    if t[0].isupper() and t[0].isalpha():
        pat = r"^([A-Z](?:\s*\.\s*\d{1,2}){%d})\s*(.*)$" % (groups - 1)
    else:
        pat = r"^(\d{1,2}(?:\s*\.\s*\d{1,2}){%d})\s*(.*)$" % (groups - 1)
    m = re.match(pat, t, re.S)
    if not m:
        return "", t
    rest = m.group(2).strip()
    # 条号后多打一个句点（JTS 147 附录写成 "C.0.1. 岩体结构类型…"）→ 去掉，否则正文以 "." 开头
    rest = re.sub(r"^[.．、]\s*", "", rest)
    return _norm(m.group(1)), rest


def _para_runs(p):
    """取段落文本（按 run 顺序拼接）。"""
    return "".join(t.text or "" for t in p.iter(W + "t"))


def _table_rows(tbl):
    """表格 → 二维列表。合并单元格按网格展开（gridSpan/vMerge 简单处理）。"""
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            txt = " ".join(_clean(_para_runs(p)) for p in tc.findall(W + "p"))
            span = 1
            tcpr = tc.find(W + "tcPr")
            if tcpr is not None:
                gs = tcpr.find(W + "gridSpan")
                if gs is not None:
                    try:
                        span = max(1, int(gs.get(W + "val") or 1))
                    except ValueError:
                        span = 1
            cells.append(_clean(txt))
            cells.extend([""] * (span - 1))
        if any(c for c in cells):
            rows.append(cells)
    return rows


def _rows_text(rows):
    return "\n".join(" | ".join(c for c in r) for r in rows)


def parse_mandatory(items):
    """从公告/制定说明区抓强制性条文条号集合。

    公告段落可能跨两段（JTS 167 就是），因此把前 120 个段落里含"强制性条文"的段落
    与它的下一段拼起来再抓号。

    ⚠ 必须用 `_norm` 判断：JTS 145 / 147-7 的原文写成"为强制 性条文"（中间有空格），
      直接用原始文本匹配 `"强制性条文"` 会漏掉整部规范的强条清单。
    返回 (set, 原始公告片段)。
    """
    head = [t for k, t in items[:120] if k == "p"]
    text = ""
    for i, t in enumerate(head):
        nt = _norm(t)
        if "强制性条文" in nt and ("第" in nt or "条" in nt):
            text = nt
            if i + 1 < len(head) and re.match(r"^[0-9]", _norm(head[i + 1])):
                text += _norm(head[i + 1])
            break
    if not text:
        return set(), ""
    nums = set()
    # 只抓"第X条/款"结构里的条号，避免把年份、页数当条号
    for m in re.finditer(r"第(\d{1,2}(?:\.\d{1,2}){1,3})[条款]", text):
        nums.add(m.group(1))
    return nums, text[:400]


def _find_body_start(items):
    """定位正文起点，跳过封面/公告/制定说明/编写人员/目次。

    ⚠ 只认首个 `1.0.1`（正文第 1 章第 1 条）。**不能认 "1 总则"**：
      JTS 167 的"制定说明"末尾有一份编写人员清单，写作 `1 总则：刘永绣`、`2 术语：…`，
      形如章标题，实测会把正文起点提前到该清单（items[27]），
      既把章名污染成"术语：刘永绣"，又让后面的图注（`1-钢筋网3～5层`）被当成第 1 章。

    不跳正文前的区块会造成两类污染（实测都出现过）：
      ① 公告里"第9.1.11条、第9.2.10条……"被当成条文，生成一条 clause=9.1.11 的假记录，
         正文里出现"条、第9.2.10条……为强制性条文"这种串味文本；
      ② 目次里的"5.1 一般规定 (48)"被当节标题，把节名带页码。
    """
    for i, (kind, t) in enumerate(items):
        if kind == "p" and _norm(t).startswith("1.0.1"):
            return i
    # 回退：严格的"1 总则"整行（不接冒号/人名）
    for i, (kind, t) in enumerate(items):
        if kind == "p" and re.match(r"^1\s*总则\s*$", _norm(t)):
            return i
    return 0


def parse_chapter_titles(items):
    r"""抓章号→章名映射：{"1": "总则", …}。

    来源为目次或制定说明末的编写人员清单（`1 总则：刘永绣`），只取冒号前的干净标题。
    ⚠ `_norm` 会把空白全部去掉（`'1 总则'` → `'1总则'`），故此处用 `\s*` 而非 `\s+`；
      靠"数字后紧跟汉字"排除图注 `1-钢筋网3～5层`、条号 `3.1.2`、年份 `2018年`。
    ⚠ 还要排除公告句被误切（JTS 120-3 曾把"…3 项水运工程强制性行业标准的公告"
      切成第 3 章"项水运工程强制性行业标准的公告"）。
    """
    out = {}
    for kind, t in items:
        if kind != "p":
            continue
        # 原文行首常带引号/引导符（实测 JTS 167 写成 "'1 总则：刘永绣"）
        s = _norm(t).lstrip("'\"‘’“”·.、 ")
        m = re.match(r"^(\d{1,2})\s*([\u4e00-\u9fff][\u4e00-\u9fff（）()、·]{0,15})(?:[：:]|$)", s)
        if not m:
            continue
        num, title = m.group(1), m.group(2)
        if int(num) > 40 or len(title) < 2:
            continue
        if any(ch in title for ch in "。；，,;="):
            continue
        if any(w in title for w in ("公告", "通知", "标准", "规范")):
            continue
        out.setdefault(num, title)
    return out


def parse_docx(path, std_code, doc_name, version, is_main):
    """解析一部 docx → (records, stats)。"""
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")

    # 1) 先把 body 摊平成 p / tbl 序列
    items = []
    for el in body:
        tag = el.tag.split("}")[-1]
        if tag == "p":
            t = _clean(_para_runs(el))
            if t:
                items.append(("p", t))
        elif tag == "tbl":
            rows = _table_rows(el)
            if rows:
                items.append(("tbl", rows))

    mand, mand_src = parse_mandatory(items)
    body_start = _find_body_start(items)
    chapter_titles = parse_chapter_titles(items)   # setdefault 先到先得：目次/编写人员先于正文

    records = []
    stats = {"clause": 0, "table": 0, "sub": 0, "skipped": 0, "backwards": 0,
             "no_section": 0}
    cur_chapter = cur_chapter_title = ""
    cur_section = cur_section_title = ""
    cur = None
    pending_table = None
    last_seq = {}            # 父级 → 最后一条的序号（连续性自检）
    truncated = False

    for kind, payload in items[body_start:]:
        if kind == "tbl":
            rows = payload
            if pending_table:
                tid, tname = pending_table
                # 表号自带章号（表5.4.8 → 5；表A.0.1 → 附录A），不继承当前章
                mlead = re.match(r"表([A-Z]|\d+)", tid)
                lead = mlead.group(1) if mlead else ""
                if lead.isalpha():
                    tchap, tchtitle = lead, "附录" + lead
                elif lead.isdigit():
                    tchap, tchtitle = lead, chapter_titles.get(lead, "")
                else:
                    tchap, tchtitle = cur_chapter, cur_chapter_title
                rec = {
                    "std_code": std_code, "doc_name": doc_name, "source_spec": version,
                    "chapter": tchap, "chapter_title": tchtitle,
                    "section": cur_section, "section_title": cur_section_title,
                    "clause": tid, "heading": tname or cur_section_title,
                    "level": "table", "is_main": is_main,
                    "text": tname or "", "table_text": _rows_text(rows),
                    "mandatory": False, "mandatory_note": "",
                }
                records.append(rec)
                stats["table"] += 1
                pending_table = None
            elif cur is not None:
                add = _rows_text(rows)
                cur["table_text"] = (cur["table_text"] + "\n" + add).strip() if cur["table_text"] else add
            continue

        t = payload
        nt = _norm(t)

        # 2) 条文说明之后不再采集（否则条号重复、正文串味）
        if nt in ("条文说明", "条文说明目次") and stats["clause"] >= 60:
            truncated = True
            break

        # 3) 表标题（用 norm 匹配：JTS 154 写成"表 3. 1. 5"）
        mt = RE_TABLE.match(nt)
        if mt and len(t) <= 60:
            tid = "表" + re.sub(r"\s+", "", mt.group(1))
            pending_table = (tid, _clean(mt.group(2)))
            continue

        # 3b) 表题在前、表号在后的排版（JTS 144-1 全篇如此）：
        #     "海船系缆力标准值表10.2.5-1" 独立成段，下一段才是表。
        #     不识别就会把整张表并进上一条的 table_text，表号查不到、条记录也变臃肿。
        mt2 = RE_TABLE_TAIL.match(nt)
        if mt2 and len(t) <= 40:
            tid = "表" + re.sub(r"\s+", "", mt2.group(2))
            pending_table = (tid, _clean(mt2.group(1)))
            continue

        # 4) 章 / 节 / 条 / 款 —— 按层级从深到浅判，避免 "3.1.2" 被当章
        #    ⚠ 必须用 _split_no 从**原文**剥离条号：JTS 154 / 144-1 排版成"3. 1. 4"，
        #      直接用 `^(\d+\.\d+\.\d+)` 匹配会整部漏条。
        no4, rest4 = _split_no(t, 4)
        if no4 and cur is not None and no4.rsplit(".", 1)[0] == cur["clause"]:
            cur["text"] += "\n" + no4 + " " + rest4
            stats["sub"] += 1
            continue

        no3, rest3 = _split_no(t, 3)
        if no4:
            # 父条记录尚未建立（父条标题段缺失，或被并入上一条）时，以父条号建档，
            # 正文保留完整款号。否则会生成"条号 5.4.12、正文以 `.2 开敞式…` 开头"的断头记录。
            no3, rest3 = no4.rsplit(".", 1)[0], no4 + " " + rest4
        if no3:
            parent = no3.rsplit(".", 1)[0]
            # 条号是强结构：正文区内一律接受。
            # 旧的"父级须与当前节同章"判定，在章切换而节标题缺失时会把整批条 skip
            # （JTS 167 曾因此漏记第 5/6/7 章多条）；错序与串味改由 backwards + 连续性自检暴露。
            if parent != cur_section:
                stats["no_section"] += 1
                cur_section, cur_section_title = parent, ""
            # 连续性：同父级下条序号应递增
            try:
                seq = int(no3.rsplit(".", 1)[1])
                if parent in last_seq and seq < last_seq[parent]:
                    stats["backwards"] += 1
                last_seq[parent] = max(seq, last_seq.get(parent, 0))
            except ValueError:
                pass
            # 章号一律由条号首段反推（不再依赖章标题识别，避免图注/编者清单污染）
            lead = no3.split(".")[0]
            if lead.isalpha():
                chap, chap_title = lead, "附录" + lead
            else:
                chap, chap_title = lead, chapter_titles.get(lead, "")
            cur = {
                "std_code": std_code, "doc_name": doc_name, "source_spec": version,
                "chapter": chap, "chapter_title": chap_title,
                "section": parent, "section_title": cur_section_title,
                "clause": no3, "heading": cur_section_title,
                "level": "clause", "is_main": is_main,
                "text": rest3, "table_text": "",
                "mandatory": no3 in mand or any(mm.startswith(no3 + ".") for mm in mand),
                "mandatory_note": "",
            }
            if no3 in mand:
                cur["mandatory_note"] = "公告列为强制性条文"
            elif cur["mandatory"]:
                sub_hit = [mm for mm in mand if mm.startswith(no3 + ".")]
                cur["mandatory_note"] = "公告列为强制性条文，仅限第 %s 款" % "、".join(sorted(sub_hit))
            if cur["mandatory"]:
                cur["mandatory_note"] += "（原文为黑体字部分；docx 黑体标记已丢失，句级范围须查原版）"
            records.append(cur)
            stats["clause"] += 1
            continue

        no2, rest2 = _split_no(t, 2)
        if no2 and len(t) <= 40 and "。" not in t:
            cur_section, cur_section_title = no2, _clean(rest2)
            continue

        no1, rest1 = _split_no(t, 1)
        # 排除年份行（"2018-03-12发布" 会被剥成章号 20）与图注（"1-钢筋网3～5层"）
        if (no1 and len(t) <= 40 and "。" not in t and no1.isdigit()
                and int(no1) <= 40 and not re.match(r"^\d{4}", t)
                and not re.match(r"^\d+\s*[-—－–]", t)):
            cur_chapter = no1
            cur_chapter_title = chapter_titles.get(no1, _clean(rest1).replace(" ", ""))
            cur_section = cur_section_title = ""
            continue

        # 5) 普通段落：并到当前条（保留款内小段）
        if cur is not None:
            cur["text"] += "\n" + t

    # 去掉 table_text 为空的键，减小体积
    for r in records:
        if not r.get("table_text"):
            r.pop("table_text", None)
    stats["truncated"] = truncated
    stats["mandatory_found"] = len(mand)
    # 款级强条（如 3.1.2.1）在库里并入所属条（3.1.2），故按"前缀命中"判是否定位
    have = {r["clause"] for r in records}
    stats["mandatory_missing"] = sorted(
        m for m in mand
        if not any(h == m or m.startswith(h + ".") for h in have)) if mand else []

    stats["mandatory_src"] = mand_src
    return records, stats


def main():
    ap = argparse.ArgumentParser(description="从 JTS 规范 docx 原文重建条文库")
    ap.add_argument("--doc-dir", default=DEFAULT_DOC_DIR, help="存放 JTS docx 的目录")
    ap.add_argument("--out", default="", help="输出 JSON 路径（默认 references/pw_clauses.json）")
    ap.add_argument("--list", action="store_true", help="只统计，不写文件")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(here, "..", "references", "pw_clauses.json")

    all_recs, spec_stats = [], OrderedDict()
    for std_code, fname, name, version, is_main in DOCS:
        path = os.path.join(args.doc_dir, fname)
        if not os.path.isfile(path):
            print("[MISS] %s -> %s" % (std_code, path), file=sys.stderr)
            spec_stats[std_code] = {"error": "missing file"}
            continue
        try:
            recs, st = parse_docx(path, std_code, name, version, is_main)
        except Exception as e:  # 单部失败不影响其余
            print("[ERR ] %s %s: %s" % (std_code, name, e), file=sys.stderr)
            spec_stats[std_code] = {"error": str(e)}
            continue
        all_recs.extend(recs)
        spec_stats[std_code] = st
        print("%-11s %-24s 条 %4d 表 %3d 款 %4d 强条 %2d 乱序 %2d 截断 %s"
              % (std_code, name, st["clause"], st["table"], st["sub"],
                 st["mandatory_found"], st["backwards"], "Y" if st["truncated"] else "N"),
              file=sys.stderr)
        if st["mandatory_missing"]:
            print("     ⚠ 强条未在正文定位：%s" % ", ".join(st["mandatory_missing"]), file=sys.stderr)

    total = len(all_recs)
    print("---- 合计 %d 块 / %d 部" % (total, len([k for k, v in spec_stats.items() if "error" not in v])),
          file=sys.stderr)

    if args.list:
        return 0

    payload = {
        "meta": {
            "domain": "水运工程",
            "source": "JTS 规范 docx 原文自动解析（非块库）",
            "spec_count": len(spec_stats),
            "chunk_count": total,
            "builder": "build_clauses.py",
        },
        "specs": spec_stats,
        "chunks": all_recs,
    }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print("写出 %s（%.1f KB）" % (out, os.path.getsize(out) / 1024.0), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
