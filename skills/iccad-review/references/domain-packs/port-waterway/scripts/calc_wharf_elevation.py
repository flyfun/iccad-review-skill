#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""码头前沿设计水深 / 设计底高程 / 前沿顶高程 复算（水运工程报告审查用）。

【它解决什么】
    报告写"码头前沿设计水深 12.5m""前沿底高程 -13.20m""码头面高程 6.50m"，
    本工具按 JTS 165—2025 的公式与表值**独立复算**，做"复算值 / 报告值"三方比对。
    水运报告最常出的两类错：① 富裕深度漏项（只算吃水+0.5m）；② 顶高程用错水位
    （拿常水位或平均高潮位当设计高水位）。

【依据】
    JTS 165—2025  5.4.11（**强条**）  码头前沿设计水深：按设计低水位时保证设计船型满载吃水安全停靠
    JTS 165—2025  5.4.12.1           D = T + Z1 + Z2 + Z3 + Z4
                                      Z2 = K1·H4% − Z1（良好掩护）；Z2 = K1·H4%（开敞）
                                      表5.4.12-1 龙骨下最小富裕深度 Z1
                                      表5.4.12-2 船舶装载纵倾富裕深度 Z3
    JTS 165—2025  5.4.12.2           开敞式大型码头 D 尚不宜小于 1.1T（宜级 → ▲ 提示）
    JTS 165—2025  5.4.13             设计底高程 = 设计起算水位 − D
    JTS 165—2025  5.4.8 / 表5.4.8    码头前沿顶高程 E = 设计水位 + Δ（上水控制标准）
                                      基本标准：设计高水位 + Δ（一般≥1.0m；掩护良好 1.0~2.0m）
                                      复核标准：极端高水位 + Δ（掩护良好 0~0.5m）

【用法】
    # 设计水深（良好掩护、淤泥质底、横浪）
    python calc_wharf_elevation.py --mode depth --t 10.5 --soil 淤泥 --h4 1.2 --k1 0.5 \
        --cover good --cargo bulk_liquid --dwt 50000 --silt 0.4 --report 12.8
    # 设计底高程
    python calc_wharf_elevation.py --mode bottom --t 10.5 --soil 岩石 --h4 0.8 --zw 2.10 --report -13.20
    # 前沿顶高程（基本标准）
    python calc_wharf_elevation.py --mode top --case basic --zw 3.80 --delta 1.2 --report 5.00

【退出码】0 满足 / 1 不满足 / 2 输入错 / 3 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表5.4.12-1 龙骨下最小富裕深度 Z1（m）——
Z1_SOIL = [
    (("淤泥",), 0.20),
    (("含淤泥", "淤泥质砂", "松砂", "粉砂"), 0.30),
    (("块状土", "黏土", "粘土", "砂土"), 0.40),
    (("岩石", "岩"), 0.60),
]

# —— 表5.4.12-2 船舶装载纵倾富裕深度 Z3（m，滚装船按吨级）——
Z3_RORO = [(1000.0, 0.30), (float("inf"), 0.20)]
Z3_BULK_LIQUID = 0.15          # 干散货船、液体散货船
Z3_SILT_MIN = 0.40             # 5.4.12.1 Z4：有淤积港口备淤深度不宜小于 0.4m
K1_ALONG, K1_CROSS = 0.3, (0.5, 0.7)   # 顺浪 / 横浪

# —— 表5.4.8 前沿顶高程富裕高度 Δ（m）——
DELTA_TOP = {
    "basic": (1.0, 2.0),       # 上水控制·基本标准：一般≥1.0；掩护良好 1.0~2.0
    "check": (0.0, 0.5),       # 上水控制·复核标准：极端高水位 + 0~0.5
    "force": (0.0, 1.0),       # 受力控制标准：设计高水位 + 0~1.0
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


def _z1(soil, gravity=False):
    """表5.4.12-1；注：重力式码头 Z1 按岩石土取（0.60）。"""
    if gravity:
        return 0.60, "重力式码头按岩石土（表5.4.12-1 注）"
    s = (soil or "").strip()
    for keys, v in Z1_SOIL:
        if any(k in s for k in keys):
            return v, "按底质“%s”" % s
    return None, "未识别底质“%s”" % s


def _z3(cargo, dwt):
    c = (cargo or "").strip().lower()
    if c in ("bulk", "liquid", "bulk_liquid", "干散货", "液体散货"):
        return Z3_BULK_LIQUID, "干散货/液体散货取 0.15m"
    if c in ("roro", "滚装", "滚装船"):
        for lim, v in Z3_RORO:
            if dwt <= lim:
                return v, "滚装船按吨级 %.0fDWT 取表5.4.12-2" % dwt
    if c in ("general", "container", "杂货", "集装箱"):
        return 0.0, "杂货船/集装箱船可不计纵倾富裕深度"
    return 0.0, "未指定货种，按不计 Z3 处理（须报告说明）"


def main():
    ap = argparse.ArgumentParser(description="码头前沿水深 / 底高程 / 顶高程复算（JTS 165—2025）")
    ap.add_argument("--mode", required=True, choices=["depth", "bottom", "top"],
                    help="depth=设计水深；bottom=设计底高程；top=前沿顶高程")
    ap.add_argument("--t", type=float, default=None, help="[depth/bottom] 设计船型满载吃水 T，m")
    ap.add_argument("--soil", default="淤泥", help="[depth/bottom] 海底底质：淤泥/含淤泥砂/块状土/岩石")
    ap.add_argument("--gravity", action="store_true", help="[depth/bottom] 重力式码头（Z1 按岩石土取 0.60）")
    ap.add_argument("--h4", type=float, default=0.0, help="[depth/bottom] 码头前允许停泊波高 H4%%，m")
    ap.add_argument("--k1", type=float, default=0.5, help="[depth/bottom] 波浪富裕系数 K1（顺浪0.3/横浪0.5~0.7）")
    ap.add_argument("--cover", default="good", choices=["good", "open", "partial"],
                    help="[depth/bottom] 掩护情况 good/open/partial")
    ap.add_argument("--z2", type=float, default=None, help="[depth/bottom] 直接给定 Z2（部分掩护时用），m")
    ap.add_argument("--cargo", default="", help="[depth/bottom] 货种：bulk_liquid/roro/general/container")
    ap.add_argument("--dwt", type=float, default=0.0, help="[depth/bottom] 船舶吨级 DWT（滚装船 Z3 用）")
    ap.add_argument("--silt", type=float, default=0.0, help="[depth] 备淤富裕深度 Z4，m（有淤积不宜小于0.4）")
    ap.add_argument("--zw", type=float, default=None, help="[bottom/top] 设计起算水位 / 设计水位，m")
    ap.add_argument("--case", default="basic", choices=["basic", "check", "force"],
                    help="[top] basic=基本标准(设计高水位) / check=复核标准(极端高水位) / force=受力控制")
    ap.add_argument("--delta", type=float, default=None, help="[top] 富裕高度 Δ，m（按表5.4.8 取值）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的结论值，用于三方比对")
    ap.add_argument("--tol", type=float, default=0.05, help="[可选] 报告值允许偏差，m（仅提示）")
    args = ap.parse_args()

    bad = []
    calc = None

    if args.mode in ("depth", "bottom"):
        if args.t is None or args.t <= 0:
            print("★ 输入错：--t 设计船型满载吃水必填且 > 0", file=sys.stderr)
            return 2
        z1, z1_note = _z1(args.soil, args.gravity)
        if z1 is None:
            print("★ 输入错：%s（可选：淤泥/含淤泥砂/块状土/岩石）" % z1_note, file=sys.stderr)
            return 2
        if args.cover == "good":
            z2 = max(0.0, args.k1 * args.h4 - z1)
            z2_src = "Z2 = K1·H4%% − Z1 = %.2f×%.2f − %.2f（良好掩护，负值取0）" % (args.k1, args.h4, z1)
        elif args.cover == "open":
            z2 = args.k1 * args.h4
            z2_src = "Z2 = K1·H4%% = %.2f×%.2f（开敞）" % (args.k1, args.h4)
        else:
            if args.z2 is None:
                print("★ 输入错：部分掩护须用 --z2 直接给定波浪富裕深度", file=sys.stderr)
                return 2
            z2 = args.z2
            z2_src = "Z2 = %.2f（部分掩护，报告给定）" % z2
        z3, z3_src = _z3(args.cargo, args.dwt)
        z4 = max(0.0, args.silt)
        d = args.t + z1 + z2 + z3 + z4

        print("=" * 64)
        print("依据            : JTS 165—2025 5.4.11（强条）/ 5.4.12.1")
        print("设计船型吃水 T  : %.2f m" % args.t)
        print("龙骨下富裕 Z1   : %.2f m  （表5.4.12-1，%s）" % (z1, z1_note))
        print("波浪富裕   Z2   : %.2f m  （%s）" % (z2, z2_src))
        print("纵倾富裕   Z3   : %.2f m  （%s）" % (z3, z3_src))
        print("备淤富裕   Z4   : %.2f m  %s" % (z4, "（有淤积港口不宜小于0.4m）" if z4 else ""))
        print("-" * 64)
        print("设计水深   D    : %.2f m  = %.2f + %.2f + %.2f + %.2f + %.2f"
              % (d, args.t, z1, z2, z3, z4))
        calc = d

        # 5.4.12.2 开敞式大型码头 D 不宜小于 1.1T —— 宜级，只提示
        if args.cover == "open" and d < 1.1 * args.t - 1e-9:
            print("  ▲ 提示：开敞式大型码头前沿设计水深不宜小于 1.1T = %.2f m（5.4.12.2，宜级）"
                  % (1.1 * args.t))

        if args.mode == "bottom":
            if args.zw is None:
                print("★ 输入错：--mode bottom 须给 --zw 设计起算水位", file=sys.stderr)
                return 2
            calc = args.zw - d
            print("设计起算水位   : %.2f m" % args.zw)
            print("设计底高程     : %.2f m  = %.2f − %.2f" % (calc, args.zw, d))

    else:  # top
        if args.zw is None:
            print("★ 输入错：--mode top 须给 --zw 设计水位", file=sys.stderr)
            return 2
        lo, hi = DELTA_TOP[args.case]
        delta = args.delta
        print("=" * 64)
        print("依据            : JTS 165—2025 5.4.8 / 表5.4.8（上水控制标准）")
        print("组合情况        : %s" % {"basic": "基本标准（设计高水位）",
                                        "check": "复核标准（极端高水位）",
                                        "force": "受力控制标准"}[args.case])
        print("设计水位       : %.2f m" % args.zw)
        if delta is None:
            print("★ 输入错：--delta 须按表5.4.8 给定（本组合参考范围 %.1f~%.1f m）" % (lo, hi),
                  file=sys.stderr)
            return 2
        if delta < lo - 1e-9 or delta > hi + 1e-9:
            print("  ▲ 提示：Δ=%.2f m 超出表5.4.8 该组合参考范围 %.1f~%.1f m，须报告说明依据"
                  % (delta, lo, hi))
        calc = args.zw + delta
        print("富裕高度   Δ   : %.2f m  （表5.4.8 参考范围 %.1f~%.1f）" % (delta, lo, hi))
        print("前沿顶高程 E   : %.2f m  = %.2f + %.2f" % (calc, args.zw, delta))

    # —— 三方比对 ——
    if args.report is not None and calc is not None:
        print("-" * 64)
        print("报告值          : %.2f m" % args.report)
        diff = args.report - calc
        print("复算值 − 报告值 : %+.2f m" % (-diff))
        if abs(diff) > args.tol:
            print("  ▲ 提示：偏差 %.2f m 超过 %.2f m，须核对报告取值与计算过程" % (diff, args.tol))
        if args.mode in ("depth", "bottom"):
            _check_min("报告值 vs 复算值", args.report, calc, bad, note="水深/底高程不得小于复算值")
        else:
            _check_min("报告顶高程", args.report, calc, bad, note="顶高程不得低于复算值")

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足（复算值 %s m）" % _fmt(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
