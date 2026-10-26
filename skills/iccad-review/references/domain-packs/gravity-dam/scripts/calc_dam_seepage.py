#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝基防渗与排水复核（混凝土重力坝报告审查用）。

【它解决什么】
    报告写 "帷幕深 45m、主排水孔深 22m、扬压力折减系数 0.25"，本工具按
    SL 319-2018 第 7.4 节逐项核：
      · curtain —— 帷幕体防渗标准 q（7.4.4 强条）与悬挂式帷幕深度 0.3~0.7 倍水头（7.4.5）；
      · drain   —— 主排水孔深 0.4~0.6 倍帷幕深且高、中坝不小于 10m（7.4.14），孔距（7.4.13）；
      · uplift  —— 按"上游→帷幕→排水→下游"折线图形算单宽扬压力合力 U（计算器，不作合格判定）。

【依据】
    SL 319-2018 7.4.4（★强条）：坝高 >100m，q=1~3Lu；50~100m，q=3~5Lu；<50m，q≤5Lu
    SL 319-2018 7.4.5：封闭式伸入相对隔水层 3~5m；悬挂式（非岩溶）0.3~0.7 倍水头
    SL 319-2018 7.4.13：主排水孔孔距 2~3m，辅助 3~5m
    SL 319-2018 7.4.14：主排水孔深 = 0.4~0.6 倍帷幕深；高、中坝不小于 10m；辅助 6~12m
    SL 319-2018 7.4.10：主排水孔与帷幕孔距离不宜小于 2m

【用法】
    python calc_dam_seepage.py --mode curtain --height 85 --h 78 --depth 42 --q 3.2
    python calc_dam_seepage.py --mode drain --height 85 --curtain-depth 42 --drain-depth 20
    python calc_dam_seepage.py --mode uplift --h 78 --b 60 --x-grout 6 --x-drain 10 --alpha1 0.30 --alpha2 0.15

【退出码】统一语义（家族约定，勿改）
    0 = 满足    1 = 不满足（含违反强条）    2 = 输入错    3 = 仅参考值（不作硬判定）

【判据方向纪律】
    · 透水率 q、孔距、排水孔深的上界 → **上限型 _check_max**
    · 帷幕深度比、排水孔深/帷幕深的下界、高坝最小孔深 → **下限型 _check_min**
    · 区间型（0.3~0.7、0.4~0.6、6~12）以**下限**作硬判定，上界只出 ▲ 提示
      （族内约定：区间上限多为经验优化方向，不宜据此否报告）。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 限值（SL 319-2018 7.4；判据方向见函数名）——
Q_LIMIT = [           # (坝高下限, 坝高上限, q 上限, q 期望下限)
    (100.0, 1e9, 3.0, 1.0),   # 坝高 >100m：q=1~3Lu
    (50.0, 100.0, 5.0, 3.0),  # 50~100m：q=3~5Lu
    (0.0, 50.0, 5.0, None),   # <50m：q≤5Lu
]
CURTAIN_RATIO = (0.3, 0.7)    # 悬挂式帷幕深/水头
DRAIN_RATIO = (0.4, 0.6)      # 主排水孔深/帷幕深
DRAIN_MIN_HM = 10.0           # 高、中坝主排水孔最小孔深，m
AUX_DRAIN_RANGE = (6.0, 12.0)
SPACING_MAIN = (2.0, 3.0)
SPACING_AUX = (3.0, 5.0)


def _fmt(v, f="%.2f"):
    return f % v if v is not None else "-"


def _check_min(name, val, lim, bad, f="%.2f", note=""):
    ok = val >= lim
    print("  %-30s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≥" if ok else "★<", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s < 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _check_max(name, val, lim, bad, f="%.2f", note=""):
    ok = val <= lim
    print("  %-30s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≤" if ok else "★>", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s > 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _q_limit(height):
    for lo, hi, qmax, qmin in Q_LIMIT:
        if lo < height <= hi:
            return qmax, qmin
    return Q_LIMIT[-1][2], Q_LIMIT[-1][3]


def main():
    ap = argparse.ArgumentParser(description="混凝土重力坝坝基防渗排水复核（SL 319-2018 7.4）")
    ap.add_argument("--mode", required=True, choices=["curtain", "drain", "uplift"],
                    help="curtain=帷幕标准与深度；drain=排水孔；uplift=扬压力图形（计算器）")
    ap.add_argument("--height", type=float, default=None, help="坝高，m")
    ap.add_argument("--h", type=float, default=None, help="[curtain/uplift] 作用水头（上游水深），m")
    ap.add_argument("--depth", type=float, default=None, help="[curtain] 设计帷幕深度，m")
    ap.add_argument("--q", type=float, default=None, help="[curtain] 帷幕体透水率，Lu")
    ap.add_argument("--karst", action="store_true", help="[curtain] 岩溶地区：不套用 0.3~0.7 倍水头经验值")
    ap.add_argument("--curtain-depth", type=float, default=None, help="[drain] 帷幕深度，m")
    ap.add_argument("--drain-depth", type=float, default=None, help="[drain] 排水孔深度，m")
    ap.add_argument("--type", default="main", choices=["main", "aux"], help="[drain] main=主排水孔；aux=辅助排水孔")
    ap.add_argument("--spacing", type=float, default=None, help="[drain] 排水孔孔距，m")
    ap.add_argument("--distance", type=float, default=None, help="[drain] 主排水孔与帷幕孔的距离，m")
    ap.add_argument("--b", type=float, default=None, help="[uplift] 坝底宽，m")
    ap.add_argument("--h2", type=float, default=0.0, help="[uplift] 下游水深，m，默认 0")
    ap.add_argument("--x-grout", type=float, default=None, help="[uplift] 帷幕至上游面距离，m")
    ap.add_argument("--x-drain", type=float, default=None, help="[uplift] 主排水孔至上游面距离，m")
    ap.add_argument("--alpha1", type=float, default=None, help="[uplift] 帷幕处扬压力折减系数")
    ap.add_argument("--alpha2", type=float, default=None, help="[uplift] 排水处扬压力折减系数")
    ap.add_argument("--gamma", type=float, default=9.81, help="[uplift] 水重度，kN/m3，默认 9.81")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的扬压力合力，kN/m")
    ap.add_argument("--tol", type=float, default=0.05, help="[可选] 三方比对允许偏差，默认 5%%")
    args = ap.parse_args()

    bad, notes = [], []

    if args.mode == "curtain":
        print("=" * 64)
        print("依据               : SL 319-2018 7.4.4（★强条）/ 7.4.5")
        if args.height is None:
            print("★ 输入错：curtain 模式需给 --height")
            return 2
        qmax, qmin = _q_limit(args.height)
        print("坝高               : %.1f m → 帷幕体透水率控制 q ≤ %.1f Lu" % (args.height, qmax))
        if args.q is not None:
            _check_max("帷幕体透水率 q", args.q, qmax, bad, note="7.4.4")
            if qmin is not None and args.q < qmin:
                print("  ▲ 提示：q=%.2fLu 低于标准区间下限 %.1fLu（防渗更强，不算错）" % (args.q, qmin))
        if args.depth is None or args.h is None:
            print("▲ 提示：未给 --depth / --h，跳过帷幕深度比复核")
        else:
            ratio = args.depth / args.h
            if args.karst:
                print("  ▲ 提示：岩溶地区帷幕深度按相对隔水层与渗漏量经论证确定，不套 0.3~0.7 经验值")
            else:
                _check_min("悬挂式帷幕深/水头", ratio, CURTAIN_RATIO[0], bad, f="%.3f", note="7.4.5")
                if ratio > CURTAIN_RATIO[1]:
                    print("  ▲ 提示：比值 %.3f 超过 0.7（帷幕偏深，宜说明经济性）" % ratio)
            print("  说明：封闭式帷幕应伸入相对隔水层 3~5m，按 7.4.5-1 单独核")

    elif args.mode == "drain":
        print("=" * 64)
        print("依据               : SL 319-2018 7.4.13 / 7.4.14")
        if args.curtain_depth is None or args.drain_depth is None:
            print("★ 输入错：drain 模式需给 --curtain-depth 与 --drain-depth")
            return 2
        if args.curtain_depth <= 0:
            print("★ 输入错：--curtain-depth 应大于 0")
            return 2
        ratio = args.drain_depth / args.curtain_depth
        if args.type == "main":
            _check_min("主排水孔深/帷幕深", ratio, DRAIN_RATIO[0], bad, f="%.3f", note="7.4.14")
            if ratio > DRAIN_RATIO[1]:
                print("  ▲ 提示：比值 %.3f 超过 0.6（孔深偏大，宜说明必要性）" % ratio)
            if args.height is not None and args.height >= 30:
                _check_min("主排水孔深（高、中坝）", args.drain_depth, DRAIN_MIN_HM, bad, note="7.4.14")
            if args.spacing is not None:
                _check_max("主排水孔孔距", args.spacing, SPACING_MAIN[1], bad, note="7.4.13")
                if args.spacing < SPACING_MAIN[0]:
                    print("  ▲ 提示：孔距 %.2fm 小于 2m（偏密，宜说明）" % args.spacing)
            # 7.4.10 原文为"不宜小于 2m"（宜级）→ 只出 ▲ 提示，不作不合格判定
            if args.distance is not None:
                if args.distance < 2.0:
                    print("  ▲ 提示：主排水孔距帷幕孔 %.2fm < 2m（7.4.10 为\"不宜小于\"，须说明理由）"
                          % args.distance)
                else:
                    print("  %-30s : %.2f  满足 7.4.10（不宜小于 2m）" % ("主排水孔距帷幕孔", args.distance))
        else:
            _check_min("辅助排水孔深", args.drain_depth, AUX_DRAIN_RANGE[0], bad, note="7.4.14")
            _check_max("辅助排水孔深", args.drain_depth, AUX_DRAIN_RANGE[1], bad, note="7.4.14")
            if args.spacing is not None:
                _check_max("辅助排水孔孔距", args.spacing, SPACING_AUX[1], bad, note="7.4.13")
                if args.spacing < SPACING_AUX[0]:
                    print("  ▲ 提示：孔距 %.2fm 小于 3m（偏密，宜说明）" % args.spacing)

    else:  # uplift
        print("=" * 64)
        print("依据               : SL 319-2018 7.4.2 / 6.3.2（扬压力计入 ΣW）")
        print("性质               : **计算器** —— 规范未给扬压力单一限值，本模式不作合格判定")
        need = [k for k, v in (("--h", args.h), ("--b", args.b), ("--x-grout", args.x_grout),
                               ("--x-drain", args.x_drain), ("--alpha1", args.alpha1),
                               ("--alpha2", args.alpha2)) if v is None]
        if need:
            print("★ 输入错：uplift 模式缺少 %s" % "、".join(need))
            return 2
        if not (0 < args.x_grout < args.x_drain < args.b):
            print("★ 输入错：应满足 0 < x-grout < x-drain < b —— 你给的是 %.2f / %.2f / %.2f"
                  % (args.x_grout, args.x_drain, args.b))
            return 2
        g = args.gamma
        u0 = g * args.h                    # 上游端
        u1 = args.alpha1 * g * args.h      # 帷幕处
        u2 = args.alpha2 * g * args.h      # 排水处
        u3 = g * args.h2                   # 下游端
        a1 = 0.5 * (u0 + u1) * args.x_grout
        a2 = 0.5 * (u1 + u2) * (args.x_drain - args.x_grout)
        a3 = 0.5 * (u2 + u3) * (args.b - args.x_drain)
        u = a1 + a2 + a3
        print("扬压力强度         : 上游 %.2f / 帷幕 %.2f / 排水 %.2f / 下游 %.2f kPa"
              % (u0, u1, u2, u3))
        print("分段面积           : 上游段 %.1f / 帷幕-排水段 %.1f / 排水-下游段 %.1f kN/m" % (a1, a2, a3))
        print("单宽扬压力合力 U   : %.1f kN/m" % u)
        if args.report is not None:
            diff = abs(u - args.report) / args.report * 100 if args.report else 0.0
            print("  %-30s : 复算 %.1f / 报告 %.1f / 差 %.1f%%  %s"
                  % ("扬压力合力(三方比对)", u, args.report, diff,
                     "一致" if diff <= args.tol * 100 else "★须核对"))
        print("=" * 64)
        print("判定：仅参考值（不作硬判定）")
        return 3

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足")
    return 0


if __name__ == "__main__":
    sys.exit(main())
