#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清淤疏浚复核器 —— SL 17-2014。

【三个功能（用 --mode 选）】
  section    断面与工程量：给断面几何 + 长度 → 断面面积 A、疏浚工程量 V
  tolerance  超深超宽校核：按挖泥船型/斗容查 SL 17 表 23 的允许值，比对报告值
  slope      边坡坡比建议：按土质类别查 SL 17 表 4 的坡比区间，比对报告坡比

【用法】
    python calc_dredge.py --mode section --shape trap --b 20 --m 3.0 --h 1.5 --length 1200
    python calc_dredge.py --mode tolerance --dredger 绞吸式 --cutter-dia 1.2 \
        --report-overwidth 0.6 --report-overdepth 0.25
    python calc_dredge.py --mode slope --soil 可塑黏土 --report-slope 0.25

退出码：0 = 满足 / 无报告值；1 = 超限。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# SL 17-2014 表 23 挖泥船超深超宽允许值（m）：(船型, 规格键) -> (超宽每边, 计算超深, 最大允许超深)
T23 = {
    ("绞吸式", "lt1.5"): (0.5, 0.3, 0.4), ("绞吸式", "1.5-2.0"): (1.0, 0.3, 0.5), ("绞吸式", "gt2.0"): (1.5, 0.4, 0.5),
    ("斗轮式", "lt1.5"): (0.3, 0.2, 0.3), ("斗轮式", "1.5-2.4"): (0.5, 0.2, 0.3), ("斗轮式", "gt2.4"): (1.0, 0.3, 0.4),
    ("链斗式", "le0.5"): (1.0, 0.2, 0.3), ("链斗式", "gt0.5"): (1.5, 0.3, 0.4),
    ("抓斗式", "lt2.0"): (0.5, 0.3, 0.4), ("抓斗式", "2.0-4.0"): (1.0, 0.4, 0.6), ("抓斗式", "gt4.0"): (1.5, 0.5, 0.8),
    ("铲扬式", "le2.0"): (1.0, 0.3, 0.4), ("铲扬式", "gt2.0"): (1.5, 0.3, 0.5),
    ("水力冲挖机组", "-"): (0.3, 0.05, 0.1),
    ("环保疏浚", "-"): (2.0, 0.1, 0.2),
}
# SL 17-2014 表 4 土质类别坡比（1:m 的 m 下限, 上限）
T4_SLOPE = {
    "强风化岩": (1.0, 1.5), "弱胶结碎石": (1.5, 2.5), "卵石": (2.5, 3.0),
    "硬塑黏土": (2.0, 3.0), "可塑黏土": (3.0, 5.0), "密实及中密实砂土": (3.0, 5.0),
    "松散及松散砂土": (5.0, 10.0), "软塑淤泥": (5.0, 25.0),
}


def bucket_key(dredger, dia):
    if dredger == "绞吸式":
        return "lt1.5" if dia < 1.5 else ("1.5-2.0" if dia <= 2.0 else "gt2.0")
    if dredger == "斗轮式":
        return "lt1.5" if dia < 1.5 else ("1.5-2.4" if dia <= 2.4 else "gt2.4")
    if dredger == "链斗式":
        return "le0.5" if dia <= 0.5 else "gt0.5"
    if dredger == "抓斗式":
        return "lt2.0" if dia < 2.0 else ("2.0-4.0" if dia <= 4.0 else "gt4.0")
    if dredger == "铲扬式":
        return "le2.0" if dia <= 2.0 else "gt2.0"
    return "-"


def main():
    ap = argparse.ArgumentParser(description="清淤疏浚复核（SL 17-2014）")
    ap.add_argument("--mode", choices=["section", "tolerance", "slope"], required=True)
    # section
    ap.add_argument("--shape", choices=["trap", "rect"], default="trap")
    ap.add_argument("--b", type=float, help="设计河底宽（m）")
    ap.add_argument("--m", type=float, default=0.0, help="边坡 m（H:V）")
    ap.add_argument("--h", type=float, help="平均疏浚厚度（m）")
    ap.add_argument("--length", type=float, help="疏浚长度（m）")
    # tolerance
    ap.add_argument("--dredger", help="挖泥船型：绞吸式/斗轮式/链斗式/抓斗式/铲扬式/水力冲挖机组/环保疏浚")
    ap.add_argument("--cutter-dia", type=float, default=0.0, help="绞刀/斗轮直径 或 斗容（m 或 m³）")
    ap.add_argument("--report-overwidth", type=float, default=None, help="报告超宽（每边,m）")
    ap.add_argument("--report-overdepth", type=float, default=None, help="报告超深（m）")
    # slope
    ap.add_argument("--soil", help="土质类别（见表4）")
    ap.add_argument("--report-slope", type=float, default=None, help="报告坡比（m，即 1:m）")
    args = ap.parse_args()

    if args.mode == "section":
        if None in (args.b, args.h, args.length):
            ap.error("section 需 --b --h --length")
        A = (args.b + args.m * args.h) * args.h if args.shape == "trap" else args.b * args.h
        V = A * args.length
        print("=" * 62)
        print("疏浚断面与工程量")
        print("=" * 62)
        print("断面: %s  底宽 b=%.2f m  边坡 m=%.2f  平均厚度 h=%.2f m" % (args.shape, args.b, args.m, args.h))
        print("断面面积 A : %.3f m²" % A)
        print("疏浚长度 L : %.0f m" % args.length)
        print("=> 工程量 V : %.1f m³  (= A×L)" % V)
        print("提示: 实际工程量按 SL 17 断面法/平均高程法计量，并计入超深超宽；此处为设计断面量。")
        return 0

    if args.mode == "tolerance":
        if not args.dredger:
            ap.error("tolerance 需 --dredger")
        key = bucket_key(args.dredger, args.cutter_dia)
        if (args.dredger, key) not in T23:
            print("未找到该船型规格的允许值（请核对 --dredger / --cutter-dia）")
            return 0
        ow, cd, md = T23[(args.dredger, key)]
        print("=" * 62)
        print("超深超宽校核（SL 17 表 23）")
        print("=" * 62)
        print("船型: %s  规格: %s" % (args.dredger, key if key != "-" else "—"))
        print("允许超宽(每边): %.2f m   计算超深: %.2f m   最大允许超深: %.2f m" % (ow, cd, md))
        fail = False
        if args.report_overwidth is not None:
            ok = args.report_overwidth <= ow + 1e-9
            print("-" * 62)
            print("报告超宽 %.2f m → %s（应 ≤ %.2f）" % (args.report_overwidth, "满足" if ok else "★ 超限", ow))
            fail = fail or (not ok)
        if args.report_overdepth is not None:
            ok = args.report_overdepth <= md + 1e-9
            print("报告超深 %.2f m → %s（应 ≤ %.2f 最大允许）" % (args.report_overdepth, "满足" if ok else "★ 超限", md))
            fail = fail or (not ok)
        print("-" * 62)
        print("结论: %s" % ("★ 超深超宽超限" if fail else ("✔ 满足" if (args.report_overwidth is not None or args.report_overdepth is not None) else "已给出允许值")))
        return 1 if fail else 0

    # slope
    if not args.soil:
        ap.error("slope 需 --soil")
    if args.soil not in T4_SLOPE:
        print("土质类别不在表4：可选 %s" % "、".join(T4_SLOPE))
        return 0
    lo, hi = T4_SLOPE[args.soil]
    print("=" * 62)
    print("疏浚边坡坡比建议（SL 17 表 4）")
    print("=" * 62)
    print("土质类别: %s" % args.soil)
    print("建议坡比: 1:%.1f ~ 1:%.1f   （即 m = %.1f ~ %.1f）" % (lo, hi, lo, hi))
    fail = False
    if args.report_slope is not None:
        ok = lo - 1e-9 <= args.report_slope <= hi + 1e-9
        print("-" * 62)
        print("报告坡比 m=%.2f → %s（应在 %.1f~%.1f）" % (
            args.report_slope, "在建议区间" if ok else "★ 偏离建议区间（过陡或过缓）", lo, hi))
        fail = not ok
    print("-" * 62)
    print("结论: %s" % ("★ 坡比偏离土质类别建议区间" if fail else ("✔ 在建议区间" if args.report_slope else "已给出建议坡比")))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
