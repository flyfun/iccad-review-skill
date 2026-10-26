#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规范条文检索工具 —— 给"报告审查"技能取"判定尺子"用（族内标准件，通用）。

【为什么需要它】
    审查报告要下"合规/不合规"的判词，就必须拿到规范条文的原文。
    本工具从《水利审查工具》(hydro_reviewer) 的规范块库里按主题捞出条文，
    供审查时引用到具体条号，避免凭记忆编条款号（编错一个就是假结论）。

【数据来源】
    默认：**技能自带的条文 JSON**（自动发现 `references/*_clauses.json`）。
        零外部依赖 —— 不需要源码树、不需要本机任何绝对路径；JSON 路径按
        本脚本所在位置定位，因此在任何目录下调用都能找到。
    可选：hydro_reviewer 的块库 chunks.pkl（全库 62 部）。仅当要查
        "自带 JSON 之外"的规范时才用，需显式传 --pkl（该路径为本机专属）。

用法：
    # 1) 看自带库里有啥（有哪些规范、各多少块）——默认即可，无需任何参数
    python spec_lookup.py --list-specs

    # 2) 查条文（关键词过滤）——默认走技能自带 JSON
    python spec_lookup.py --spec "<主规范号>" --q <关键词>
    #    多个规范可以逗号分隔一起查
    python spec_lookup.py --spec "GB 50201,SL 252" --q 防洪标准

    # 3) 指定别的 JSON（可选）
    python spec_lookup.py --from-json other.json --q 超高

    # 4) 改用本机块库查全库 62 部（可选，需 hydro_reviewer 源码树）
    python spec_lookup.py --pkl "C:\\...\\chunks.pkl" --spec "SL 252" --q 级别

    # 5) 把筛选结果导出成纯数据 JSON
    python spec_lookup.py --spec "<主规范号>" --export out.json

    # 6) 完全静默（诊断默认走 stderr，stdout 只留条文正文）
    python spec_lookup.py --spec "<主规范号>" --q <关键词> --quiet

【输出约定】
    诊断信息（loaded / matched / exported）一律写 **stderr**，stdout 只保留条文正文，
    因此 stdout 可直接管道或计量载入量，不必再手动剔除表头。

【查询纪律（重要）】
    1) query 为 **去空白 + 忽略大小写** 的字面包含匹配（不是分词、不是语义检索）。
       因此 `--q 阻水比` 能命中库内写作"阻 水 比"的条文；但**同义词不通用**——
       `--q 坡式护岸` 在 GB 50707 里查不到（那是 GB 50286 的词）。
    2) **别带"表"字查条号**：库内 clause 字段是 `7.2.4` 这种纯数字，带"表"会 0 命中。
    3) 优先用**规范原文的术语词组**，别用单字（单字命中过多，白白塞满上下文）。
    4) 命中数看 stderr 的 `matched: N (of M)`；N 过大就换更窄的词。
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
#    自动发现 references/*_clauses.json —— 于是同一份标准件可用于**任何**域技能，
#    不必按域改文件名（族内命名：dam/sluice/swc/rc/flood/ps…_clauses.json）。
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _discover_json():
    refdir = os.path.join(SKILL_ROOT, "references")
    try:
        import glob
        cands = sorted(glob.glob(os.path.join(refdir, "*_clauses.json")))
    except Exception:
        cands = []
    return cands[0] if cands else os.path.join(refdir, "clauses.json")


DEFAULT_JSON = _discover_json()

# —— 可选数据源：hydro_reviewer 的块库（仅在需要查"自带 JSON 之外"的规范时才用）——
DEFAULT_PKL = r"C:\Users\Administrator\水利审查工具\specs_db\chunks.pkl"   # 块库位置
DEFAULT_SRC = r"D:\重构文件v9.4\hydro_reviewer"                            # 主源码根
FALLBACK_SRC = r"F:\报告审查\重构文件v9.1.54\hydro_reviewer"                # 备用源码根

FIELDS = ("std_code", "doc_name", "source_spec", "chapter", "section",
          "clause", "level", "layer", "domain", "text", "section_text", "table_text")


def _diag(msg, quiet=False):
    """诊断信息一律写 stderr —— stdout 只留条文正文，便于管道与计量载入量。"""
    if not quiet:
        print(msg, file=sys.stderr)


def _norm(s):
    """归一化字符串：转字符串 → 去掉所有空白 → 转大写（模糊匹配用）。"""
    return "".join(str(s or "").split()).upper()


def load_chunks(pkl_path, src_candidates):
    """加载块库；为能正常反序列化，先把源码根加进 sys.path。"""
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
    """排序键：先按"有无条款号"（有条款号的排前），再按正文长度降序。"""
    has_clause = 1 if str(d.get("clause") or "").strip() else 0
    return (-has_clause, -len(str(d.get("text") or "")))


def make_sort_key(query):
    """带查询的排序键：**条号精确命中优先**。

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
    """过滤判定：spec 片段匹配 std_code/doc_name/source_spec；
    query 匹配 text/section_text —— **去空白 + 忽略大小写**的字面包含。

    为什么去空白：库内正文多来自 PDF/OCR，中文词常被拆成"阻 水 比"这类带空格形态，
    若按原始串做字面包含，`--q 阻水比` 会漏掉最关键的 5.2.2 条（那条正是"阻 水 比"）。
    归一化后 `--q "阻水比"` 与 `--q "阻 水 比"` 等价，召回更稳。
    """
    if spec:
        specs = [s for s in str(spec).split(",") if s.strip()]
        blob = _norm(d.get("std_code")) + _norm(d.get("doc_name")) + _norm(d.get("source_spec"))
        if not any(_norm(s) in blob for s in specs):
            return False
    if query:
        text = _norm("".join(str(d.get(k) or "") for k in
                             ("clause", "section", "text", "section_text")))
        if _norm(query) not in text:
            return False
    return True


def render(d):
    """把一条命中记录渲染成人读的文本块。"""
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
    ap = argparse.ArgumentParser(description="规范条文检索（报告审查用 · 族内标准件）")
    ap.add_argument("--pkl", default=os.environ.get("SPECS_DB"),
                    help="[可选] 块库 chunks.pkl 路径；传了则改用块库(pickle)源查全库")
    ap.add_argument("--src", default=os.environ.get("HYDRO_SRC"),
                    help="[可选] hydro_reviewer 源码根（pickle 反序列化用）")
    ap.add_argument("--from-json", default=None,
                    help="[可选] 指定条文 JSON；默认自动发现技能自带 references/*_clauses.json")
    ap.add_argument("--spec", default=None,
                    help="规范编号/名称片段，如 'SL/T 808'、'防洪标准'（可逗号分隔多个）")
    ap.add_argument("--q", default=None, help="条文关键词，如 '阻水比'、'壅水'、'净空'")
    ap.add_argument("--limit", type=int, default=20, help="最多输出条数")
    ap.add_argument("--mandatory-only", action="store_true",
                    help="只输出强制性条文（依据公告回填的 mandatory 字段；块库源无此字段则返回空）")
    ap.add_argument("--list-specs", action="store_true", help="列出库内规范及块数")
    ap.add_argument("--export", default=None, help="把筛选结果导出为纯数据 JSON")
    ap.add_argument("--quiet", action="store_true",
                    help="抑制诊断信息；诊断默认走 stderr，stdout 只留条文正文")
    args = ap.parse_args()

    if args.pkl:
        chunks = load_chunks(args.pkl, [args.src or DEFAULT_SRC, FALLBACK_SRC])
        _diag("loaded chunks: %d (pickle)" % len(chunks), args.quiet)
        items = [to_dict(c) for c in chunks]
    else:
        json_path = args.from_json or DEFAULT_JSON
        if not os.path.isfile(json_path):
            raise SystemExit("条文 JSON 不存在：%s\n（先跑 scripts/build_clauses.py 生成 references/*_clauses.json，"
                             "或用 --from-json 指定）" % json_path)
        with open(json_path, encoding="utf-8") as f:
            pool = json.load(f)
        items = pool.get("chunks", pool) if isinstance(pool, dict) else pool
        _diag("loaded from json: %d records (%s)" % (len(items), os.path.basename(json_path)), args.quiet)

    if args.list_specs:
        c = Counter((d.get("std_code"), d.get("doc_name")) for d in items)
        for (code, name), n in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print("%-16s %-48s %6d" % (code or "-", (name or "-")[:46], n))
        return

    hits = [d for d in items if match_dict(d, args.spec, args.q)]
    if args.mandatory_only:
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
