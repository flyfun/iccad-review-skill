#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝基面抗滑稳定复核（混凝土重力坝报告审查用）。

【它解决什么】
    报告给出 "K′=3.2，满足要求"，本工具按 SL 319-2018 第 6.4.1 条独立复算，
    做 **复算值 / 规范限值 / 报告值** 三方比对，不采信报告结论。
    两类稳定分开核：
      · 坝基面滑动  —— 抗剪断公式给 K′，抗剪公式给 K（两条路线限值不同，勿混）；
      · 坝基深层滑动 —— 抗剪断仍用表 6.4.1-1，抗剪用 **表 6.4.3**（2018 新增）。

【依据】
    SL 319-2018 6.4.1 + 表 6.4.1-1（K′：基本 3.0 / 特殊(1) 2.5 / 特殊(2) 2.3）
    SL 319-2018 6.4.1 + 表 6.4.1-2（K：按 1/2/3 级与组合，见下表）
    SL 319-2018 6.4.3 + 表 6.4.3（深层抗滑 K：基本 1.35/1.30/1.25 等）
    公式：K′ =（f′ΣW + c′A）/ ΣP ；K = fΣW / ΣP

【用法】
    # 坝基面，抗剪断
    python calc_dam_stability.py --mode surface --method shear-strength \\
        --w 52000 --p 16000 --f 0.85 --c 900 --a 60 --combo basic

    # 坝基面，抗剪（按坝级）
    python calc_dam_stability.py --mode surface --method shear-friction \\
        --w 52000 --p 16000 --f 0.62 --grade 2 --combo special1

    # 深层抗滑（报告已算出 K 或 K′）
    python calc_dam_stability.py --mode deep --method shear-friction \\
        --value 1.28 --grade 1 --combo basic

    # 三方比对
    ... --report 3.2 --tol 0.05

【退出码】统一语义（家族约定，勿改）
    0 = 满足    1 = 不满足（含违反强条）    2 = 输入错    3 = 仅参考值

【判据方向纪律】
    抗滑稳定安全系数是**下限型**（越大越好）→ 一律 _check_min。
    把方向判反（"小于限值才合格"）即为错情。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 限值表（SL 319-2018；判据方向：下限型，≥ 为满足）——
# 表 6.4.1-1 坝基面抗滑稳定安全系数 K′（不分坝级）
LIMIT_KP = {"basic": 3.0, "special1": 2.5, "special2": 2.3}

# 表 6.4.1-2 坝基面抗滑稳定安全系数 K（按坝级）
LIMIT_K = {
    "basic":    {1: 1.10, 2: 1.05, 3: 1.05},
    "special1": {1: 1.05, 2: 1.00, 3: 1.00},
    "special2": {1: 1.00, 2: 1.00, 3: 1.00},
}

# 表 6.4.3 坝基深层抗滑稳定安全系数 K（抗剪公式；抗剪断仍用表 6.4.1-1）
LIMIT_DEEP = {
    "basic":    {1: 1.35, 2: 1.30, 3: 1.25},
    "special1": {1: 1.20, 2: 1.15, 3: 1.10},
    "special2": {1: 1.10, 2: 1.05, 3: 1.05},
}

COMBO_NAME = {
    "basic": "基本组合",
    "special1": "特殊组合（1）",
    "special2": "特殊组合（2）拟静力法",
}


def _fmt(v, f="%.2f"):
    return f % v if v is not None else "-"


def _check_min(name, val, lim, bad, f="%.2f", note=""):
    """下限型判据：val 应 ≥ lim。不满足则记入 bad（rc=1）。"""
    ok = val >= lim
    print("  %-28s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≥" if ok else "★<", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s < 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _check_max(name, val, lim, bad, f="%.2f", note=""):
    """上限型判据：val 应 ≤ lim。不满足则记入 bad（rc=1）。"""
    ok = val <= lim
    print("  %-28s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≤" if ok else "★>", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s > 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _compare_report(name, computed, report, tol, notes):
    """三方比对：只出提示，不置换硬判定（报告值可能与取参口径不同）。"""
    if report is None:
        return
    diff = abs(computed - report)
    flag = "一致" if diff <= (tol if tol is not None else 0.05) else "★须核对"
    print("  %-28s : 复算 %s / 报告 %s / 差 %.3f  %s"
          % (name + "(三方比对)", _fmt(computed), _fmt(report), diff, flag))
    if flag != "一致":
        notes.append("%s 复算 %s 与报告 %s 差 %.3f" % (name, _fmt(computed), _fmt(report), diff))


def main():
    ap = argparse.ArgumentParser(description="混凝土重力坝抗滑稳定复核（SL 319-2018 6.4）")
    ap.add_argument("--mode", required=True, choices=["surface", "deep"],
                    help="surface=坝基面滑动；deep=坝基深层滑动")
    ap.add_argument("--method", default="shear-strength",
                    choices=["shear-strength", "shear-friction"],
                    help="shear-strength=抗剪断（f′、c′）；shear-friction=抗剪（f）")
    ap.add_argument("--combo", default="basic", choices=["basic", "special1", "special2"],
                    help="荷载组合：basic / special1 / special2（拟静力法）")
    ap.add_argument("--grade", type=int, default=None, choices=[1, 2, 3],
                    help="坝的级别（抗剪公式与深层抗滑按级别取限值）")
    ap.add_argument("--w", type=float, default=None, help="ΣW：作用于滑动面的法向分值，kN（含扬压力）")
    ap.add_argument("--p", type=float, default=None, help="ΣP：作用于滑动面的切向分值，kN")
    ap.add_argument("--f", type=float, default=None, help="摩擦系数：抗剪断为 f′，抗剪为 f")
    ap.add_argument("--c", type=float, default=None, help="抗剪断凝聚力 c′，kPa（仅抗剪断用）")
    ap.add_argument("--a", type=float, default=None, help="坝基接触面截面积 A，m2（仅抗剪断用）")
    ap.add_argument("--value", type=float, default=None, help="[deep 模式] 已算得或报告给出的 K（抗剪）或 K′（抗剪断）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的安全系数，用于三方比对")
    ap.add_argument("--tol", type=float, default=None, help="[可选] 三方比对允许偏差，默认 0.05")
    args = ap.parse_args()

    bad, notes = [], []
    rc = 0
    combo_cn = COMBO_NAME[args.combo]

    if args.mode == "surface":
        print("=" * 62)
        print("依据               : SL 319-2018 6.4.1 及表 6.4.1-1 / 表 6.4.1-2")
        print("荷载组合           : %s" % combo_cn)

        if args.method == "shear-strength":
            miss = [k for k, v in (("--w", args.w), ("--p", args.p),
                                   ("--f", args.f), ("--c", args.c), ("--a", args.a)) if v is None]
            if miss:
                print("★ 输入错：抗剪断复算缺少 %s" % "、".join(miss))
                return 2
            if args.p <= 0:
                print("★ 输入错：--p 应大于 0（切向荷载为 0 时抗滑稳定无意义）")
                return 2
            k = (args.f * args.w + args.c * args.a) / args.p
            lim = LIMIT_KP[args.combo]
            print("复算               : K′ =（f′ΣW + c′A）/ ΣP =（%.3f×%.1f + %.1f×%.1f）/ %.1f = %.3f"
                  % (args.f, args.w, args.c, args.a, args.p, k))
            _check_min("坝基面抗剪断 K′", k, lim, bad)
            _compare_report("坝基面抗剪断 K′", k, args.report, args.tol, notes)
        else:
            miss = [k for k, v in (("--w", args.w), ("--p", args.p), ("--f", args.f)) if v is None]
            if miss:
                print("★ 输入错：抗剪复算缺少 %s" % "、".join(miss))
                return 2
            if args.grade is None:
                print("★ 输入错：抗剪公式的限值按坝级取值，必须给 --grade")
                return 2
            if args.p <= 0:
                print("★ 输入错：--p 应大于 0")
                return 2
            k = args.f * args.w / args.p
            lim = LIMIT_K[args.combo][args.grade]
            print("复算               : K = fΣW / ΣP = %.3f×%.1f / %.1f = %.3f"
                  % (args.f, args.w, args.p, k))
            _check_min("坝基面抗剪 K（%d 级）" % args.grade, k, lim, bad)
            _compare_report("坝基面抗剪 K", k, args.report, args.tol, notes)

    else:  # deep
        print("=" * 62)
        print("依据               : SL 319-2018 6.4.3 及表 6.4.3（抗剪）/ 表 6.4.1-1（抗剪断）")
        print("荷载组合           : %s" % combo_cn)
        if args.value is None:
            print("★ 输入错：deep 模式需给 --value（已算得或报告给出的安全系数）")
            return 2

        if args.method == "shear-strength":
            lim = LIMIT_KP[args.combo]
            label = "深层抗剪断 K′"
            print("说明               : 6.4.3 规定深层抗剪断仍按表 6.4.1-1 控制")
        else:
            if args.grade is None:
                print("★ 输入错：深层抗剪限值按坝级取值，必须给 --grade")
                return 2
            lim = LIMIT_DEEP[args.combo][args.grade]
            label = "深层抗剪 K（%d 级）" % args.grade
            print("说明               : 6.4.3 规定深层抗剪按表 6.4.3 控制（2018 版新增）")
        print("取用值             : %s" % _fmt(args.value))
        _check_min(label, args.value, lim, bad)

    print("=" * 62)
    if notes:
        print("▲ 三方比对提示：%s" % "；".join(notes))
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足")
    return rc


if __name__ == "__main__":
    sys.exit(main())
