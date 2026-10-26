#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""航道设计水深 / 设计底高程 / 最小弯曲半径 复算（水运工程报告审查用）。

【它解决什么】
    报告写"航道设计水深 9.8m""航道底高程 −10.50m""最小弯曲半径 1200m"，本工具按
    JTS 165—2025 6.4.5 与 JTS 181—2016 4.5.5 独立复算。
    常见错：① 把"通航水深 D0"当"设计水深 D"（漏备淤深度 Z4）；
            ② Z2 不看船浪夹角、不按 10000 吨级以下加 25%；
            ③ 弯曲半径只按货船算，忽略顶推船队长度的 3 倍。

【依据】
    JTS 165—2025  6.4.5.1   D0 = T + Z0 + Z1 + Z2 + Z3 ；D = D0 + Z4
                             表6.4.5-1 航行时龙骨下最小富裕深度 Z1（土质 × 吨级）
                             表6.4.5-2 船、浪夹角与 Z2/H4 变化系数
                             注：10000 吨级以下船舶 Z2 数值应增加 25%
    JTS 165—2025  6.4.5.4   Z = H − D（航道设计底高程 = 设计通航水位 − 设计水深）
    JTS 181—2016  4.5.5     最小弯曲半径：取 3×顶推船队长、4×货船长、4×拖带船队最大单船长之大值；
                             困难河段不得小于 2/3/3 倍之大值；流速>3m/s 山区河流宜 5 倍
    JTS 181—2016  4.5.2     H = T + ΔH（内河航道水深；富裕水深查表4.5.2）

【用法】
    python calc_channel_depth.py --mode depth --t 8.5 --z0 0.35 --soil 淤泥 --dwt 30000 \
        --angle 30 --h4 1.0 --period 8 --cargo bulk_liquid --silt 0.5 --report 10.2
    python calc_channel_depth.py --mode bottom --t 8.5 --z0 0.35 --soil 岩石 --dwt 30000 --zw 3.20
    python calc_channel_depth.py --mode radius --push 180 --ship 150 --tow 120 --report 800

【退出码】0 满足 / 1 不满足 / 2 输入错 / 3 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表6.4.5-1 航行时龙骨下最小富裕深度 Z1（m）——
#   土质 → [<5000, 5k~10k, 10k~50k, 50k~100k, 100k~300k, ≥300k]
Z1_TABLE = [
    (("淤泥", "软塑", "可塑", "松散砂"), (0.20, 0.20, 0.30, 0.40, 0.50, 0.60)),
    (("硬塑", "中密砂"), (0.30, 0.30, 0.40, 0.50, 0.60, 0.70)),
    (("坚硬黏性", "密实砂", "强风化"), (0.40, 0.40, 0.50, 0.60, 0.70, 0.80)),
    (("风化岩", "岩石"), (0.50, 0.60, 0.60, 0.80, 0.80, 0.90)),
]
DWT_BANDS = [5000, 10000, 50000, 100000, 300000]

# —— 表6.4.5-2 Z2/H4 ——（船浪夹角 0~90；T≤8 与 T≈10 两行）
Z2_RATIO = {
    0: (0.24, 0.55), 10: (0.32, 0.65), 20: (0.38, 0.75), 30: (0.42, 0.83),
    40: (0.44, 0.90), 50: (0.46, 0.97), 60: (0.48, 1.02), 70: (0.49, 1.08),
    80: (0.50, 1.10), 90: (0.52, 1.15),
}
Z2_SMALL_BOAT_FACTOR = 1.25      # 注①：10000 吨级以下 Z2 增加 25%
Z3_BULK_LIQUID = 0.15
Z4_SILT_MIN = 0.40


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


def _z1(soil, dwt):
    for keys, vals in Z1_TABLE:
        if any(k in soil for k in keys):
            idx = 0
            for i, lim in enumerate(DWT_BANDS):
                if dwt < lim:
                    idx = i
                    break
            else:
                idx = len(DWT_BANDS)
            band = "≥%d" % DWT_BANDS[-1] if idx == len(DWT_BANDS) else "<%d" % DWT_BANDS[idx]
            return vals[idx], "土质“%s”·吨级 %s（表6.4.5-1）" % (soil, band)
    return None, "未识别土质“%s”" % soil


def _z2_ratio(angle, period):
    a = min(Z2_RATIO, key=lambda k: abs(k - angle))
    r8, r10 = Z2_RATIO[a]
    if period is None or period <= 8:
        return r8, a, "T≤8 行"
    if period >= 10:
        return r10, a, "T=10 行（T>10 须专门论证）"
    # 8<T<10 内插
    t = (period - 8) / 2.0
    return r8 + (r10 - r8) * t, a, "8<T<10 内插"


def main():
    ap = argparse.ArgumentParser(description="航道设计水深 / 底高程 / 弯曲半径复算（JTS 165 / JTS 181）")
    ap.add_argument("--mode", required=True, choices=["depth", "bottom", "radius"])
    ap.add_argument("--t", type=float, default=None, help="[depth/bottom] 设计船型满载吃水 T，m")
    ap.add_argument("--z0", type=float, default=0.0, help="[depth/bottom] 船体下沉量 Z0，m（图6.4.5）")
    ap.add_argument("--soil", default="淤泥", help="[depth/bottom] 土质")
    ap.add_argument("--dwt", type=float, default=30000.0, help="[depth/bottom] 船舶吨级 DWT")
    ap.add_argument("--angle", type=float, default=90.0, help="[depth/bottom] 船、浪夹角，°")
    ap.add_argument("--h4", type=float, default=0.0, help="[depth/bottom] 波高 H4%%，m")
    ap.add_argument("--period", type=float, default=None, help="[depth/bottom] 波浪平均周期 T，s")
    ap.add_argument("--cargo", default="bulk_liquid", help="[depth/bottom] bulk_liquid / general / container")
    ap.add_argument("--silt", type=float, default=0.0, help="[depth] 备淤深度 Z4，m")
    ap.add_argument("--zw", type=float, default=None, help="[bottom] 设计通航水位，m")
    ap.add_argument("--push", type=float, default=None, help="[radius] 顶推船队长度，m")
    ap.add_argument("--ship", type=float, default=None, help="[radius] 货船长度，m")
    ap.add_argument("--tow", type=float, default=None, help="[radius] 拖带船队最大单船长度，m")
    ap.add_argument("--hard", action="store_true", help="[radius] 特殊困难河段（2/3/3 倍）")
    ap.add_argument("--mountain", action="store_true", help="[radius] 流速>3m/s 山区河流（5 倍）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告结论值")
    ap.add_argument("--tol", type=float, default=0.05, help="[可选] 报告值允许偏差（仅提示）")
    args = ap.parse_args()

    bad, calc = [], None

    if args.mode in ("depth", "bottom"):
        if args.t is None or args.t <= 0:
            print("★ 输入错：--t 必填且 > 0", file=sys.stderr)
            return 2
        z1, z1_src = _z1(args.soil, args.dwt)
        if z1 is None:
            print("★ 输入错：%s" % z1_src, file=sys.stderr)
            return 2
        ratio, a_used, row = _z2_ratio(args.angle, args.period)
        z2 = ratio * args.h4
        z2_note = "Z2/H4=%.2f（夹角%d°，%s）× H4=%.2f" % (ratio, a_used, row, args.h4)
        if args.dwt < 10000:
            z2 *= Z2_SMALL_BOAT_FACTOR
            z2_note += "；10000吨级以下 ×1.25（表6.4.5-2 注①）"
        z3 = Z3_BULK_LIQUID if args.cargo in ("bulk", "liquid", "bulk_liquid") else 0.0
        z4 = max(0.0, args.silt)
        d0 = args.t + args.z0 + z1 + z2 + z3
        d = d0 + z4

        print("=" * 64)
        print("依据            : JTS 165—2025 6.4.5.1")
        print("设计船型吃水 T  : %.2f m" % args.t)
        print("船体下沉量 Z0   : %.2f m" % args.z0)
        print("龙骨下富裕 Z1   : %.2f m  （%s）" % (z1, z1_src))
        print("波浪富裕   Z2   : %.2f m  （%s）" % (z2, z2_note))
        print("纵倾富裕   Z3   : %.2f m" % z3)
        print("-" * 64)
        print("通航水深   D0   : %.2f m" % d0)
        print("备淤深度   Z4   : %.2f m  %s" % (z4, "（有淤积不宜小于0.4m）" if z4 else ""))
        print("设计水深   D    : %.2f m" % d)
        calc = d
        if z4 and 0 < z4 < Z4_SILT_MIN - 1e-9:
            print("  ▲ 提示：备淤深度 %.2f m 小于 0.4m（6.4.5.1，有淤积港口不宜小于 0.4m）" % z4)

        if args.mode == "bottom":
            if args.zw is None:
                print("★ 输入错：--mode bottom 须给 --zw 设计通航水位", file=sys.stderr)
                return 2
            calc = args.zw - d
            print("设计通航水位   : %.2f m" % args.zw)
            print("航道设计底高程 : %.2f m  = %.2f − %.2f" % (calc, args.zw, d))

    else:  # radius
        vals = []
        if args.push:
            vals.append(("顶推船队长×%d" % (2 if args.hard else 3), (2 if args.hard else 3) * args.push))
        if args.ship:
            vals.append(("货船长×%d" % (3 if args.hard else 4), (3 if args.hard else 4) * args.ship))
        if args.tow:
            vals.append(("拖带最大单船×%d" % (3 if args.hard else 4), (3 if args.hard else 4) * args.tow))
        if not vals:
            print("★ 输入错：--push/--ship/--tow 至少给一个", file=sys.stderr)
            return 2
        print("=" * 64)
        print("依据            : JTS 181—2016 4.5.5%s" % ("（特殊困难河段）" if args.hard else ""))
        for name, v in vals:
            print("  %-16s : %.0f m" % (name, v))
        calc = max(v for _, v in vals)
        print("-" * 64)
        print("最小弯曲半径   : %.0f m（取大值）" % calc)
        if args.mountain:
            print("  ▲ 提示：流速>3m/s 山区性河流宜取 5 倍 → %.0f m" % (5 * max(
                [x for x in (args.push, args.ship, args.tow) if x] or [0])))

    if args.report is not None and calc is not None:
        print("-" * 64)
        print("报告值          : %s" % _fmt(args.report))
        print("复算值 − 报告值 : %+.2f" % (calc - args.report))
        if abs(calc - args.report) > args.tol:
            print("  ▲ 提示：偏差超过 %.2f，须核对取值" % args.tol)
        if args.mode == "radius":
            _check_min("报告弯曲半径", args.report, calc, bad, f="%.0f", note="不得小于复算值")
        else:
            _check_min("报告值 vs 复算值", args.report, calc, bad, note="水深/底高程不得小于复算值")

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足（复算值 %s）" % _fmt(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
