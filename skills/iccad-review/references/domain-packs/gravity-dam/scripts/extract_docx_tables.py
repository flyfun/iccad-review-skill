#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 .docx 报告里提取表格（按网格重建，正确处理合并单元格）。

【为什么需要它】
    审水土保持报告，很多判据落在报告自带的表格上——土石方平衡表、弃渣场特性表、
    工程量表、排水沟断面表、监测点布设表。直接把 docx 的 `<w:t>` 顺序拼起来会
    丢掉"哪一行哪一列"，行列错位后根本没法核对。
    本工具用 XML 解析把每个表**还原成真正的网格**：横向合并（gridSpan）按跨度展开、
    纵向合并（vMerge）用上一行同列的值补齐——这样读到的是"表"，不是"一串字"。

【与审查流程的关系】
    技能假设"报告文本已就绪"。要拿到报告文本，docx 需先解析：
      - 正文段落：`python extract_docx_tables.py report.docx --text-only`
      - 表格（推荐）：`python extract_docx_tables.py report.docx --keyword 排水沟`
    再交给 SKILL.md 第 0.5 步的取判据 / 复算脚本核对。

用法：
    # 列出全部表（可能很多）
    python extract_docx_tables.py report.docx

    # 只导正文含关键词的表（审什么查什么）
    python extract_docx_tables.py report.docx --keyword 排水沟 弃渣
    python extract_docx_tables.py report.docx --keyword 土石方

    # 只导所有正文段落（非表格文本）
    python extract_docx_tables.py report.docx --text-only

    # 导出到文件
    python extract_docx_tables.py report.docx --keyword 弃渣 --out 弃渣表.txt
"""
import argparse
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# 控制台按 UTF-8 输出，避免 GBK 报错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def elem_text(el):
    """元素下所有 <w:t> 文本拼接。"""
    return ''.join(t.text or '' for t in el.iter(W + 't'))


def parse_table(tbl):
    """把一个 <w:tbl> 还原成网格：返回行列表，每行是与网格列对齐的字符串列表。

    - gridSpan：横向跨 n 列，值重复填到 n 个槽位
    - vMerge：'restart' 起始，'continue' 沿用上一行同列的值
    """
    raw = []
    for tr in tbl.findall(W + 'tr'):
        slots = []
        col = 0
        for tc in tr.findall(W + 'tc'):
            tcPr = tc.find(W + 'tcPr')
            span, vmerge = 1, None
            if tcPr is not None:
                gs = tcPr.find(W + 'gridSpan')
                if gs is not None:
                    span = int(gs.get(W + 'val'))
                vm = tcPr.find(W + 'vMerge')
                if vm is not None:
                    vmerge = vm.get(W + 'val') or 'continue'
            slots.append((col, span, vmerge, elem_text(tc).strip()))
            col += span
        raw.append(slots)

    ncol = 1
    for r in raw:
        if r:
            ncol = max(ncol, r[-1][0] + r[-1][1])

    out, prev = [], [''] * ncol
    for r in raw:
        line = [''] * ncol
        for (c, span, vm, txt) in r:
            val = prev[c] if (vm == 'continue' and c < len(prev)) else txt
            for k in range(span):
                if c + k < ncol:
                    line[c + k] = val
        out.append(line)
        prev = line
    return out


def iter_paragraphs(root):
    """产出所有正文段落文本（不含表格内文本）。"""
    for p in root.iter(W + 'p'):
        # 跳过嵌在表格里的段落
        txt = elem_text(p).strip()
        if txt:
            yield txt


def main():
    ap = argparse.ArgumentParser(description="从 .docx 提取表格（网格重建）或正文")
    ap.add_argument("docx", help="docx 报告路径")
    ap.add_argument("--keyword", nargs="*", default=None,
                    help="只导正文含这些关键词的表格（可多个）")
    ap.add_argument("--text-only", action="store_true", help="只导正文段落，不导表格")
    ap.add_argument("--out", default=None, help="输出到文件（默认打印到屏幕）")
    args = ap.parse_args()

    z = zipfile.ZipFile(args.docx)
    root = ET.fromstring(z.read('word/document.xml'))

    buf = []
    if args.text_only:
        for txt in iter_paragraphs(root):
            buf.append(txt)
    else:
        tbls = list(root.iter(W + 'tbl'))
        buf.append("total tables: %d" % len(tbls))
        for i, tbl in enumerate(tbls):
            full = ''.join(elem_text(tc) for tc in tbl.iter(W + 'tc'))
            if args.keyword and not any(k in full for k in args.keyword):
                continue
            buf.append("=" * 70)
            buf.append("### table %d | head: %s" % (i, full[:60]))
            for row in parse_table(tbl):
                buf.append(" | ".join(row))
            buf.append("")

    text = "\n".join(buf)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("written -> %s (%d chars)" % (args.out, len(text)))
    else:
        print(text)


if __name__ == '__main__':
    main()
