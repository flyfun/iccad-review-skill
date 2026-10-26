#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桩基（单桩轴向承载力设计值 / 按单桩计算的桩距）复算（水运工程报告审查用）。

【它解决什么】
    报告写"单桩轴向承载力设计值 3200kN"，但只给极限值或只给经验参数。本工具按
    JTS 167—2018 4.2.7 与表4.2.7 复算设计值（Qa = Qk/γR），并核桩距是否允许按单桩计算。

【依据】
    JTS 167—2018  4.2.2 / 表4.2.2  中心距 ≥ 表列值可按单桩计算，否则按群桩
                                    打入桩、灌注桩（轴向）6d；或 3d~6d 且桩端进入良好持力层
                                    打入桩、灌注桩（水平）6d~8d
                                    嵌岩桩（轴向）以嵌岩段受力为主 2d；覆盖层承较大轴向力 3d
    JTS 167—2018  4.2.6            单桩轴向承载力除三种情形外应根据静载荷试验确定
    JTS 167—2018  4.2.7.1          Qa = Qk / γR
                                    Qk 单桩轴向极限承载力标准值（n≥2 且 max/min≤1.3 取平均）
    JTS 167—2018  表4.2.7          γR：打入桩 静载1.30~1.40 / 经验1.45~1.55
                                    灌注桩 静载1.50~1.60 / 经验1.55~1.65
                                    嵌岩桩抗压 静载1.60~1.70
    JTS 167—2018  4.2.18           负摩阻力判别三种情形
    JTS 167—2018  4.3.4            泥面以上桩长较大或软土层 cu<10kPa、可液化土 → 须验算压屈

【用法】
    python calc_pile_capacity.py --mode axial --qk 4200 --pile driven --method test --load 3000
    python calc_pile_capacity.py --mode axial --qk 4200 --pile bored --method empirical --report 2600
    python calc_pile_capacity.py --mode spacing --d 1.2 --s 6.0 --pile driven --axial

【退出码】0 满足 / 1 不满足 / 2 输入错 / 3 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表4.2.7 单桩轴向承载力抗力分项系数 γR ——
GAMMA_R = {
    # 桩型: (静载试验法, 经验参数法)
    "driven": ((1.30, 1.40), (1.45, 1.55)),      # 打入桩
    "bored": ((1.50, 1.60), (1.55, 1.65)),       # 灌注桩
    "rock": ((1.60, 1.70), (1.60, 1.70)),        # 嵌岩桩（抗压）
}
# —— 表4.2.2 按单桩计算的最小中心距（×d）——
SPACING_MIN = {
    ("driven", "axial"): (6.0, 3.0),    # (常规值, 放宽值；放宽须桩端进入良好持力层)
    ("driven", "lateral"): (6.0, 8.0),
    ("bored", "axial"): (6.0, 3.0),
    ("bored", "lateral"): (6.0, 8.0),
    ("rock", "axial"): (2.0, 3.0),      # 2d 以嵌岩段为主；3d 覆盖层承较大轴向力
    ("rock", "lateral"): (2.0, 8.0),
}


def _fmt(v, f="%.2f"):
    return f % v if v is not None else "-"


def _check_min(name, val, lim, bad, f="%.2f", note=""):
    ok = val >= lim - 1e-9
    print("  %-24s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≥" if ok else "★<", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s < 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def main():
    ap = argparse.ArgumentParser(description="桩基承载力与桩距复算（JTS 167—2018 第4章）")
    ap.add_argument("--mode", required=True, choices=["axial", "spacing"])
    ap.add_argument("--qk", type=float, default=None, help="[axial] 单桩轴向极限承载力标准值 Qk，kN")
    ap.add_argument("--pile", default="driven", choices=["driven", "bored", "rock"], help="桩型")
    ap.add_argument("--method", default="test", choices=["test", "empirical"],
                    help="[axial] 承载力确定方法：test=静载试验 / empirical=经验参数")
    ap.add_argument("--gamma", type=float, default=None, help="[axial] 直接给定 γR（覆盖表值）")
    ap.add_argument("--load", type=float, default=None, help="[axial] 报告的单桩轴向荷载/设计值，kN")
    ap.add_argument("--d", type=float, default=None, help="[spacing] 桩径（圆桩）或边长（方桩），m")
    ap.add_argument("--s", type=float, default=None, help="[spacing] 桩中心距，m")
    ap.add_argument("--axial", action="store_true", help="[spacing] 按轴向承载桩判（默认水平）")
    ap.add_argument("--good-bearing", action="store_true",
                    help="[spacing] 桩端进入良好持力层（允许 3d~6d 按单桩）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告结论值")
    args = ap.parse_args()

    bad, calc = [], None

    if args.mode == "axial":
        if args.qk is None or args.qk <= 0:
            print("★ 输入错：--qk 必填且 > 0", file=sys.stderr)
            return 2
        lo, hi = GAMMA_R[args.pile][0 if args.method == "test" else 1]
        g = args.gamma if args.gamma else (lo + hi) / 2.0
        if args.gamma and not (lo - 1e-9 <= args.gamma <= hi + 1e-9):
            print("  ▲ 提示：γR=%.2f 超出表4.2.7 范围 %.2f~%.2f，须说明依据" % (g, lo, hi))
        qa = args.qk / g
        calc = qa
        print("=" * 64)
        print("依据            : JTS 167—2018 4.2.7.1 + 表4.2.7")
        print("桩型            : %s" % {"driven": "打入桩", "bored": "灌注桩", "rock": "嵌岩桩"}[args.pile])
        print("确定方法        : %s" % ("静载荷试验法" if args.method == "test" else "经验参数法"))
        print("极限承载力 Qk   : %.0f kN" % args.qk)
        print("抗力分项系数 γR : %.2f  （表4.2.7 范围 %.2f~%.2f）" % (g, lo, hi))
        print("-" * 64)
        print("承载力设计值 Qa : %.0f kN  = %.0f / %.2f" % (qa, args.qk, g))
        if args.load is not None:
            _check_min("Qa vs 单桩荷载", qa, args.load, bad, f="%.0f",
                       note="设计值须不小于荷载设计值")
        if args.pile == "rock":
            print("  ▲ 说明：嵌岩桩若覆盖层与嵌岩段分别取值，须按表4.2.7 分段计算")

    else:  # spacing
        if args.d is None or args.s is None:
            print("★ 输入错：--d 与 --s 必填", file=sys.stderr)
            return 2
        kind = "axial" if args.axial else "lateral"
        normal, relaxed = SPACING_MIN[(args.pile, kind)]
        ratio = args.s / args.d
        calc = ratio
        print("=" * 64)
        print("依据            : JTS 167—2018 4.2.2 / 表4.2.2")
        print("桩型            : %s" % {"driven": "打入桩/灌注桩", "bored": "灌注桩", "rock": "嵌岩桩"}[args.pile])
        print("受力类型        : %s" % ("轴向承载" if args.axial else "水平承载"))
        print("桩径/边长 d     : %.2f m" % args.d)
        print("中心距   s      : %.2f m" % args.s)
        print("-" * 64)
        print("桩距比 s/d      : %.2f" % ratio)
        if args.pile == "rock":
            print("表4.2.2 要求    : %.0fd（嵌岩段为主）~ %.0fd（覆盖层承较大轴向力）" % (normal, relaxed))
            limit = normal
        elif kind == "axial":
            print("表4.2.2 要求    : %.0fd；或 3d~6d 且桩端进入良好持力层" % normal)
            limit = relaxed if args.good_bearing else normal
        else:
            print("表4.2.2 要求    : %.0fd~%.0fd" % (normal, relaxed))
            limit = normal
        _check_min("s/d vs 按单桩门槛", ratio, limit, bad, note="低于门槛应按群桩计算")

    if args.report is not None and calc is not None:
        print("-" * 64)
        print("报告值          : %s" % _fmt(args.report))
        print("复算值          : %s" % _fmt(calc))
        if args.mode == "axial":
            _check_min("报告值 vs 复算值", args.report, calc, bad, f="%.0f",
                       note="报告设计值不得大于复算值")
            # 报告值大于复算值 → 偏不安全，对上式再判一次更直观
            if args.report > calc + 1e-9:
                print("  ★ 报告 %0.f kN 大于复算设计值 %.0f kN，承载力取值偏大" % (args.report, calc))

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足（复算值 %s）" % _fmt(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
