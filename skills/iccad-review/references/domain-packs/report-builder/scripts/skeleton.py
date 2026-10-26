#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告审查技能脚手架 —— 按"域卡片"一键生成一部新技能的同构骨架。

【它解决什么】
    水利审查族（土石坝/水闸/水保/河道/洪评…）已固化出**同构**结构：
    SKILL.md(<5000字符) + 7~9 册 references + 零依赖 scripts + skill-meta.yaml。
    手工照抄易走形（漏载入锚点、漏分册、字数超标、脚本缺退出码语义）。
    本脚本把"结构"一键铺好，把"域内容"留成 TODO 交回人填。

【用法】
    python skeleton.py --card domain-card.json --out "C:\\...\\自建skill"
    # 或最小命令行：
    python skeleton.py --name pump-station-report-review --title 泵站工程报告审查 \
        --domain 泵站工程 --main-spec "GB 50265" --main-spec-name 泵站设计标准 --out <目录>

【域卡片(JSON)字段】
    必填：name / title / domain / main_spec / main_spec_name
    常用：title_full / domain_types / json_name / tables_file / works_file /
          block_count / cross_pairs / error_count / triggers / exclude /
          specs([[code,name],...]) / calc([[file,说明],...]) / tables_desc / lib_summary
    缺省：json_name=<前缀>_clauses.json、tables_file/works_file 由前缀推、
          block_count=12、cross_pairs=8、error_count=20

【产出】
    <out>/<name>/
      SKILL.md  skill-meta.yaml
      references/ {checklist,norms,compulsory-clauses,error-patterns,limits}.md
                  + <tables_file> + <works_file>   （模板带 TODO，待填域内容）
      scripts/ spec_lookup.py extract_docx_tables.py build_clauses.py
               + calc_*.py（按 calc 清单，从 calc_script.py.tmpl 渲染）
    并打印**待办清单**（骨架未含的域内容）。
"""
import argparse
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.dirname(HERE)
TMPL = os.path.join(BUILDER, "templates")

# 前缀用主规范代码推导（GB 50265 → gp? 不够准）；改由 name 前缀或显式给。


def _read_card(args):
    card = {}
    if args.card:
        with open(args.card, encoding="utf-8") as f:
            card = json.load(f)
    for k, v in (("name", args.name), ("title", args.title), ("domain", args.domain),
                 ("main_spec", args.main_spec), ("main_spec_name", args.main_spec_name),
                 ("json_name", args.json_name), ("tables_file", args.tables_file),
                 ("works_file", args.works_file)):
        if v:
            card[k] = v
    return card


def _prefix(name):
    """技能名去掉 -report-review，得到短前缀（river-channel-report-review → rc）。"""
    short = name.replace("-report-review", "")
    parts = [p for p in short.split("-") if p]
    if len(parts) >= 2:
        return "".join(p[0] for p in parts).lower()
    return (parts[0][:4] if parts else "xx").lower()


def build_ctx(card):
    name = card["name"]
    pf = card.get("prefix") or _prefix(name)
    specs = [tuple(x) for x in card.get("specs", [])]
    calc = [tuple(x) for x in card.get("calc", [])]
    triggers = card.get("triggers") or [card["domain"]]
    exclude = card.get("exclude") or []

    ctx = dict(card)
    ctx.setdefault("prefix", pf)
    ctx.setdefault("title_full", card.get("title_full") or card["title"])
    ctx.setdefault("domain_types", card.get("domain_types") or (card["domain"] + "设计 / 安全评价"))
    ctx.setdefault("json_name", "%s_clauses.json" % pf)
    ctx.setdefault("tables_file", "%s_tables.md" % pf)
    ctx.setdefault("works_file", "%s_works_tables.md" % pf)
    ctx.setdefault("block_count", card.get("block_count", 12))
    ctx.setdefault("cross_pairs", card.get("cross_pairs", 8))
    ctx.setdefault("error_count", card.get("error_count", 20))
    ctx.setdefault("spec_count", len(specs))
    ctx.setdefault("calc_count", len(calc))
    ctx.setdefault("lib_count", card.get("lib_summary") or ("%d 部" % len(specs)))
    ctx.setdefault("lib_summary", "%d 部 / 约 M 块（重建后以 --list-specs 实测为准）" % len(specs))
    ctx.setdefault("specs_summary", "%s %s 主规范 + 配套，共 %d 部" % (
        card["main_spec"], card["main_spec_name"], len(specs)))
    ctx.setdefault("tables_desc", card.get("tables_desc") or "限值 / 系数 / 分级")
    ctx.setdefault("calc_summary", " / ".join((c[1] if len(c) > 1 else c[0].replace("calc_", "").replace(".py", ""))
                                              for c in calc) or "（待列）")
    ctx.setdefault("triggers_inline", "、".join('"%s"' % t for t in triggers))
    ctx.setdefault("exclude_inline", "、".join(exclude) if exclude else "（待列）")
    ctx.setdefault("compulsory_inline",
                   "%s 等规范公告明示的强条" % card["main_spec"] if specs else "（待列）")

    # 多行块
    ctx["specs_block"] = "\n".join(
        '    ("%s", "%s"),%s' % (c, n, "  # ★主规范" if c == card["main_spec"] else "")
        for c, n in specs) or '    # TODO: ("GB XXXXX", "规范全名"),\n    ("", "水利工程建设标准强制性条文"),'
    ctx["calc_table"] = "\n".join(
        "| `%s` | %s |" % (f, d) for f, d in calc) or "| `calc_<x>.py` | TODO |"
    def _dedupe(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x); out.append(x)
        return out

    ctx["applicable_types"] = "\n".join(
        "  - %s" % t for t in _dedupe(card.get("applicable_types") or [card["domain"]]))
    ctx["trigger_keywords"] = "\n".join("  - %s" % t for t in _dedupe(triggers))
    ctx["exclude_domains"] = "\n".join("  - %s" % e for e in _dedupe(exclude)) or "  - TODO"
    return ctx


def render(text, ctx):
    """替换 {{KEY}}（**大小写不敏感**，模板常用大写、ctx 键为小写）。

    未知键保留为可见 TODO 标记，便于发现漏配。
    """
    out, i = [], 0
    while True:
        j = text.find("{{", i)
        if j < 0:
            out.append(text[i:])
            break
        k = text.find("}}", j)
        if k < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        key = text[j + 2:k].strip().lower()
        out.append(str(ctx[key]) if key in ctx else "<<TODO:%s>>" % key)
        i = k + 2
    return "".join(out)


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    ap = argparse.ArgumentParser(description="报告审查技能脚手架")
    ap.add_argument("--card", help="域卡片 JSON")
    ap.add_argument("--name"); ap.add_argument("--title"); ap.add_argument("--domain")
    ap.add_argument("--main-spec"); ap.add_argument("--main-spec-name")
    ap.add_argument("--json-name"); ap.add_argument("--tables-file"); ap.add_argument("--works-file")
    ap.add_argument("--out", default=os.getcwd(), help="输出父目录（默认当前目录）")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    args = ap.parse_args()

    card = _read_card(args)
    for k in ("name", "title", "domain", "main_spec", "main_spec_name"):
        if not card.get(k):
            raise SystemExit("缺少必填字段：%s（用 --card 或 --%s）" % (k, k.replace("_", "-")))
    ctx = build_ctx(card)

    root = os.path.join(args.out, card["name"])
    if os.path.isdir(root) and not args.force:
        raise SystemExit("目标已存在：%s（加 --force 覆盖）" % root)
    os.makedirs(root, exist_ok=True)

    # 1) SKILL.md 与 skill-meta.yaml
    _write(os.path.join(root, "SKILL.md"),
           render(open(os.path.join(TMPL, "SKILL.md.tmpl"), encoding="utf-8").read(), ctx))
    _write(os.path.join(root, "skill-meta.yaml"),
           render(open(os.path.join(TMPL, "skill-meta.yaml.tmpl"), encoding="utf-8").read(), ctx))

    # 2) references
    for t, dst in (("checklist.md.tmpl", "checklist.md"),
                   ("norms.md.tmpl", "norms.md"),
                   ("compulsory-clauses.md.tmpl", "compulsory-clauses.md"),
                   ("error-patterns.md.tmpl", "error-patterns.md"),
                   ("limits.md.tmpl", "limits.md"),
                   ("tables.md.tmpl", ctx["tables_file"]),
                   ("works_tables.md.tmpl", ctx["works_file"])):
        _write(os.path.join(root, "references", dst),
               render(open(os.path.join(TMPL, t), encoding="utf-8").read(), ctx))

    # 3) scripts：标准件复制 + build_clauses 渲染 + calc 模板渲染
    os.makedirs(os.path.join(root, "scripts"), exist_ok=True)
    for f in ("spec_lookup.py", "extract_docx_tables.py"):
        shutil.copy2(os.path.join(HERE, f), os.path.join(root, "scripts", f))
    _write(os.path.join(root, "scripts", "build_clauses.py"),
           render(open(os.path.join(TMPL, "build_clauses.py.tmpl"), encoding="utf-8").read(), ctx))
    for f, _d in [tuple(x) for x in card.get("calc", [])]:
        _write(os.path.join(root, "scripts", f),
               render(open(os.path.join(TMPL, "calc_script.py.tmpl"), encoding="utf-8").read(), ctx))

    # 4) 交付脚本（标准件）
    shutil.copy2(os.path.join(HERE, "deliver.py"), os.path.join(root, "scripts", "deliver.py"))

    # 5) 打印待办
    print("已生成骨架 -> %s" % root)
    print("-" * 64)
    n = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in sorted(fn):
            fp = os.path.join(dp, f); n += 1
            print("   %8d  %s" % (os.path.getsize(fp), os.path.relpath(fp, root)))
    print("-" * 64)
    print("共 %d 个文件。**下一步（骨架未含的域内容，必须人工填）**：" % n)
    print("  1) 定域：确认主规范章节数 → 定分块数；列规格清单(SPECS)与复算器清单；")
    print("  2) 建库：先跑 scripts/build_clauses.py 生成 %s（或先填 SPECS 再跑）" % ctx["json_name"]);
    print("  3) 填 references/ 各册的 TODO（判定标准必须落到 规则号+表号+数值）；")
    print("  4) 实现 scripts/calc_*.py（判据方向：下限型 _check_min / 上限型 _check_max）；")
    print("  5) SKILL.md 删净 <<TODO:…>> 并把正文压到 <5000 字符；")
    print("  6) 交付三关：python scripts/deliver.py --name %s --check" % card["name"])
    todo = [str(x) for x in _scan_todo(root)]
    if todo:
        print("-" * 64); print("骨架内 TODO 计数（%d 处，须清零）：" % len(todo))
        for t in todo: print("   ", t)


def _scan_todo(root):
    """统计骨架内未填的 TODO。**模式由拼接构造**，避免匹配到本函数自身的字面量。"""
    import re
    pat = re.compile("<<TO" + "DO:|<!" + "-- TO" + "DO|# TO" + "DO")
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", "templates")]
        for f in fn:
            fp = os.path.join(dp, f)
            try:
                s = open(fp, encoding="utf-8").read()
            except Exception:
                continue
            c = len(pat.findall(s))
            if c:
                yield "%s (%d)" % (os.path.relpath(fp, root), c)


if __name__ == "__main__":
    main()
