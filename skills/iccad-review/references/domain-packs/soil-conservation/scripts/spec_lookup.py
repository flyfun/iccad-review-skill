#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规范条文检索工具 —— 给水土保持报告审查取"判定尺子"用。

【为什么需要它】
    审查报告要下"合规/不合规"的判词，就必须拿到规范条文的原文。
    本工具从《水利审查工具》(hydro_reviewer) 的规范块库里按主题捞出条文，
    供审查时引用到具体条号，避免凭记忆编条款号（编错一个就是假结论）。

【数据来源】
    默认：技能自带的条文 JSON（references/swc_clauses.json，5 部水保规范 + 强条汇编）。
        零外部依赖——不需要源码树、不需要本机任何绝对路径；JSON 路径按
        本脚本所在位置定位，因此在任何目录下调用都能找到。
    可选：hydro_reviewer 的块库 chunks.pkl（全库 62 部）。仅当要查
        "自带 JSON 之外"的规范时才用，需显式传 --pkl（该路径为本机专属）。

    注意：**GB 50433-2018 / GB/T 50434-2018 两部核心标准不在块库中**，
        其关键条文与限值另固化在 references/swc_tables.md，用本工具查不到。

用法：
    # 1) 看自带库里有啥（有哪些规范、各多少块）——默认即可，无需任何参数
    python spec_lookup.py --list-specs

    # 2) 查条文（关键词过滤）——默认走技能自带 JSON
    python spec_lookup.py --spec "GB 51018" --q 弃渣场
    python spec_lookup.py --spec "水土保持工程设计规范" --limit 50
    #    多个规范可以逗号分隔一起查
    python spec_lookup.py --spec "GB 51018,SL 575" --q 防洪标准

    # 3) 指定别的 JSON（可选）
    python spec_lookup.py --from-json other.json --q 表土

    # 4) 改用本机块库查全库 62 部（可选，需 hydro_reviewer 源码树）
    python spec_lookup.py --pkl "C:\\...\\chunks.pkl" --spec "SL 190" --q 容许

    # 5) 把筛选结果导出成纯数据 JSON
    python spec_lookup.py --spec "GB 51018" --export out.json
    # 6) 完全静默（诊断默认走 stderr，stdout 只留条文正文）
    python spec_lookup.py --spec "GB 51018" --q 关键词 --quiet

【输出约定】
    诊断信息（loaded / matched / exported）一律写 **stderr**，stdout 只保留条文正文，
    因此 stdout 可直接管道或计量载入量，不必再手动剔除表头。
"""
import argparse
import json
import os
import pickle
import sys
from collections import Counter

# Windows 控制台默认可能是 GBK，打印中文条文会乱码/报错；
# 这里尽量切到 UTF-8 并把无法编码的字符替换掉（失败也不影响主流程）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 默认数据源：技能自带的条文 JSON（相对本脚本定位，与当前工作目录无关）——
# 这样无论从哪里调用都找得到，且不需要本机任何外部路径。
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_JSON = os.path.join(SKILL_ROOT, "references", "swc_clauses.json")

# —— 可选数据源：hydro_reviewer 的块库（仅在需要查"自带 JSON 之外"的规范时才用）——
# 注意：以下三条是本机专属绝对路径，换机器会失效；只有显式传 --pkl 才会走这条路径。
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"   # 块库位置
DEFAULT_SRC = r"D:\重构文件v9.4\hydro_reviewer"                            # 主源码根
FALLBACK_SRC = r"F:\报告审查\重构文件v9.1.54\hydro_reviewer"                # 备用源码根

# 从块对象里抽取的字段（缺哪个留空，不会因字段缺失而报错）
#   std_code/doc_name/source_spec —— 规范身份（编号/文件名/来源规范）
#   chapter/section/clause        —— 条款定位（章/节/条号）
#   level/layer/domain            —— 层级/层次/领域标签
#   text/section_text/table_text  —— 正文/章节正文/表格正文
FIELDS = ("std_code", "doc_name", "source_spec", "chapter", "section",
          "clause", "level", "layer", "domain", "text", "section_text", "table_text")


def _diag(msg, quiet=False):
    """诊断信息一律写 stderr —— stdout 只留条文正文，便于管道与计量载入量。"""
    if not quiet:
        print(msg, file=sys.stderr)


def _norm(s):
    """归一化字符串：转字符串 → 去掉所有空白 → 转大写。

    用于模糊匹配——这样 "GB 51018" / "gb51018" / "GB/T 51018" 这类写法差异
    都能对上，避免因为空格或大小写搜不到。
    """
    return "".join(str(s or "").split()).upper()


def load_chunks(pkl_path, src_candidates):
    """加载块库；为能正常反序列化，先把源码根加进 sys.path。

    pickle 反序列化时会按"类定义所在的模块路径"去 import，
    所以必须让 hydro_reviewer 的 src 目录可被 import，否则会 ModuleNotFoundError。
    """
    if not os.path.isfile(pkl_path):
        raise FileNotFoundError("块库不存在：%s" % pkl_path)
    for root in src_candidates:
        if root and os.path.isdir(root):
            for p in (os.path.join(root, "src"), root):
                if os.path.isdir(p) and p not in sys.path:
                    sys.path.insert(0, p)
    with open(pkl_path, "rb") as f:
        return pickle.load(f)


def to_dict(ch):
    """把块对象转成普通 dict（只保留 FIELDS 里的字段，缺失的置 None）。"""
    return {k: getattr(ch, k, None) for k in FIELDS}


def sort_key(d):
    """排序键：先按"有无条款号"（有条款号的排前），再按正文长度降序。

    理由：报告审查最想要的是"实体条文"，它们通常带条号且正文较长；
    纯标题类小块的参考价值低，压到后面。
    """
    has_clause = 1 if str(d.get("clause") or "").strip() else 0
    return (-has_clause, -len(str(d.get("text") or "")))


def make_sort_key(query):
    """带查询的排序键：**条号/表号精确命中优先**。

    为什么需要：`--q 5.4.18` 这类条号查询，字面包含会把"正文里提到表5.4.18"的
    5.5.5 条排到前面（实测），真正的 5.4.18 条反而落到第 2 位。
    条号查询是审查里最高频的用法，必须让 `clause == q` 排第一。
    """
    qn = _norm(query).lstrip("表")

    def key(d):
        cl = _norm(d.get("clause")).lstrip("表")
        exact = 1 if qn and cl == qn else 0
        prefix = 1 if qn and cl and cl.startswith(qn + ".") else 0
        has_clause = 1 if cl else 0
        return (-exact, -prefix, -has_clause, -len(str(d.get("text") or "")))

    return key


def match_dict(d, spec, query):
    """针对"普通 dict"的过滤判定（当前主用）。

    spec  —— 规范片段匹配：把 spec 逗号拆开，任一片段出现在
             std_code/doc_name/source_spec 的任一字段里即通过
    query —— 条文字面包含：关键词出现在 text 或 section_text 里
    """
    if spec:
        specs = [s for s in str(spec).split(",") if s.strip()]
        blob = _norm(d.get("std_code")) + _norm(d.get("doc_name")) + _norm(d.get("source_spec"))
        if not any(_norm(s) in blob for s in specs):
            return False
    if query:
        # 去空白 + 忽略大小写 的字面包含：库内正文多来自 PDF/OCR，中文词常被拆成
        # "阻 水 比" 这类带空格形态；不归一化会漏掉最关键的条（阻水比/压实度/安全加高等）。
        text = _norm("".join(str(d.get(k) or "") for k in
                             ("clause", "section", "text", "section_text")))
        if _norm(query) not in text:
            return False
    return True


def render(d):
    """把一条命中记录渲染成人读的文本块：标签 + 条款定位 + 正文（+ 附表/节选）。"""
    parts = []
    tag = d.get("std_code") or d.get("doc_name") or "?"
    loc = " ".join(x for x in (
        str(d.get("chapter") or "").strip(),
        str(d.get("section") or "").strip(),
        str(d.get("clause") or "").strip(),
    ) if x)
    parts.append("【%s】%s" % (tag, loc or "(无条款定位)"))
    text = str(d.get("text") or "").strip()
    if text:
        parts.append(text)
    for extra in ("section_text", "table_text"):
        v = str(d.get(extra) or "").strip()
        if v:
            parts.append("[%s] %s" % (extra, v[:300]))
    return "\n".join(parts)


def main():
    """命令行入口：取数据源 → 过滤 → 排序 → 输出/导出。"""
    ap = argparse.ArgumentParser(description="规范条文检索（水土保持审查用）")
    ap.add_argument("--pkl", default=os.environ.get("SPECS_DB"),
                    help="[可选] 块库 chunks.pkl 路径；传了则改用块库(pickle)源查全库")
    ap.add_argument("--src", default=os.environ.get("HYDRO_SRC"),
                    help="[可选] hydro_reviewer 源码根（pickle 反序列化用）")
    ap.add_argument("--from-json", default=None,
                    help="[可选] 指定条文 JSON；默认用技能自带 references/swc_clauses.json")
    ap.add_argument("--spec", default=None,
                    help="规范编号/名称片段，如 'GB 51018'、'水土保持工程设计规范'（可逗号分隔多个）")
    ap.add_argument("--q", default=None, help="条文关键词，如 '弃渣场'、'表土'")
    ap.add_argument("--limit", type=int, default=20, help="最多输出条数")
    ap.add_argument("--mandatory-only", action="store_true",
                    help="只输出强制性条文（库内需有 mandatory 字段；本域未回填则直接报错）")
    ap.add_argument("--list-specs", action="store_true", help="列出库内规范及块数")
    ap.add_argument("--export", default=None, help="把筛选结果导出为纯数据 JSON")
    ap.add_argument("--quiet", action="store_true",
                    help="抑制诊断信息；诊断默认走 stderr，stdout 只留条文正文")
    args = ap.parse_args()

    # —— 取数据源 ——
    if args.pkl:
        chunks = load_chunks(args.pkl, [args.src or DEFAULT_SRC, FALLBACK_SRC])
        _diag("loaded chunks: %d (pickle)" % len(chunks), args.quiet)
        items = [to_dict(c) for c in chunks]
    else:
        json_path = args.from_json or DEFAULT_JSON
        if not os.path.isfile(json_path):
            raise SystemExit("条文 JSON 不存在：%s" % json_path)
        with open(json_path, encoding="utf-8") as f:
            pool = json.load(f)
        items = pool.get("chunks", pool) if isinstance(pool, dict) else pool
        _diag("loaded from json: %d records (%s)" % (len(items), os.path.basename(json_path)), args.quiet)

    # —— 分支一：只列规范清单 ——
    if args.list_specs:
        c = Counter((d.get("std_code"), d.get("doc_name")) for d in items)
        for (code, name), n in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print("%-16s %-48s %6d" % (code or "-", (name or "-")[:46], n))
        return

    # —— 分支二：按 spec/query 过滤 ——
    hits = [d for d in items if match_dict(d, args.spec, args.q)]
    if args.mandatory_only:
        # 防御性校验：块库源的 level=="mandatory" 只是"正文含'应'字"的启发式标记，
        # 不等于强条（照它写"违反强制性条文"就是假结论）。库内若无 mandatory 字段，
        # 必须报错退出——静默返回 0 条会被误读成"本规范无强条"。
        if not any("mandatory" in d for d in items):
            raise SystemExit(
                "--mandatory-only 在本域不可用：条文库未回填 mandatory 字段。\n"
                "  注意 level==\"mandatory\" 是\"正文含'应'字\"的启发式标记，不是强条。\n"
                "  强条原文：python spec_lookup.py --spec \"GB-强条汇编\" --q <关键词>\n"
                "  强条清单：references/compulsory-clauses.md（逐条核对后再下判词）\n"
                )
        hits = [d for d in hits if d.get("mandatory")]
    hits.sort(key=make_sort_key(args.q))
    _diag("matched: %d (of %d)" % (len(hits), len(items)), args.quiet)

    if args.export:
        src_desc = ("pickle:%s" % args.pkl) if args.pkl else ("json:%s" % (args.from_json or DEFAULT_JSON))
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump({"source": src_desc, "spec": args.spec, "q": args.q,
                       "count": len(hits), "chunks": hits}, f, ensure_ascii=False, indent=1)
        _diag("exported -> %s" % args.export, args.quiet)

    for d in hits[:args.limit]:
        print("-" * 50)
        print(render(d))


if __name__ == "__main__":
    main()
