#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝基面垂直应力复核（混凝土重力坝报告审查用）。

【它解决什么】
    报告给出 "坝踵 σ=0.12MPa、坝趾 σ=1.85MPa，满足要求"，本工具按
    SL 319-2018 6.3.2 的**材料力学法**独立复算坝踵/坝趾垂直应力，
    并按 6.3.3（强条）与 6.3.10（强条）逐项判定：
      · 坝踵不得出现拉应力（运用期）；
      · 坝趾不得大于混凝土容许压应力，也不得大于基岩容许承载力；
      · 抗压安全系数：基本组合 ≥4.0、特殊组合（不含地震）≥3.5。

【依据】
    SL 319-2018 6.3.2：σy = ΣW/A ± ΣM·x/J
    SL 319-2018 6.3.3（★强条）：坝踵不出现拉应力；坝趾 ≤ 混凝土容许压应力且 ≤ 基岩容许承载力；施工期坝趾拉应力 <0.1MPa
    SL 319-2018 6.3.10（★强条）：抗压安全系数 基本 4.0 / 特殊（不含地震）3.5；抗拉 4.0；地震拟静力 3.5、2.08；动力 2.3、1.0

【用法】
    # 单位坝长（1m）复算，给坝底宽与合力作用点位置
    python calc_dam_stress.py --mode base --w 52000 --b 60 --xr 19.5 \
        --allow-concrete 4.0 --allow-rock 5.0 --fc 20 --combo basic

    # 施工期
    python calc_dam_stress.py --mode base --w 48000 --b 60 --xr 20 --stage construction

    # 只算容许应力
    python calc_dam_stress.py --mode allow --fc 20 --combo basic

【退出码】统一语义（家族约定，勿改）
    0 = 满足    1 = 不满足（含违反强条）    2 = 输入错    3 = 仅参考值

【判据方向纪律】
    坝踵压应力、抗压安全系数是**下限型**（越大越好）→ _check_min；
    坝趾压应力 vs 容许值是**上限型** → _check_max。方向判反即为错情。

【重要口径】
    ΣW 必须**含扬压力**（6.3.2 明文"包括扬压力"）。漏扬压力会让坝踵应力偏大、
    坝趾偏小，正好把"坝踵拉应力"这条强条掩盖掉——这是本域最常见的漏检。
    偏心距以**合力作用点至上游面距离 xr** 输入，避免"向下游为正/为负"的口径歧义。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 限值（SL 319-2018 6.3.3 / 6.3.10；判据方向见函数名）——
K_COMP_BASIC = 4.0        # 抗压安全系数，基本组合，下限
K_COMP_SPECIAL = 3.5      # 抗压安全系数，特殊组合（不含地震），下限
K_TENSILE = 4.0           # 抗拉安全系数，下限
K_QUASI_COMP, K_QUASI_TENS = 3.5, 2.08     # 地震拟静力法
K_DYN_COMP, K_DYN_TENS = 2.3, 1.0          # 地震动力法
TENSILE_CONSTRUCTION = 0.1  # 施工期坝趾允许拉应力上限，MPa


def _fmt(v, f="%.3f"):
    return f % v if v is not None else "-"


def _check_min(name, val, lim, bad, f="%.3f", note=""):
    """下限型判据：val 应 ≥ lim。不满足则记入 bad（rc=1）。"""
    ok = val >= lim
    print("  %-30s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≥" if ok else "★<", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s < 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _check_max(name, val, lim, bad, f="%.3f", note=""):
    """上限型判据：val 应 ≤ lim。不满足则记入 bad（rc=1）。"""
    ok = val <= lim
    print("  %-30s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≤" if ok else "★>", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s > 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _compare_report(name, computed, report, tol, notes, f="%.3f"):
    if report is None:
        return
    diff = abs(computed - report)
    flag = "一致" if diff <= (tol if tol is not None else 0.02) else "★须核对"
    print("  %-30s : 复算 %s / 报告 %s / 差 %s  %s"
          % (name + "(三方比对)", _fmt(computed, f), _fmt(report, f), _fmt(diff, f), flag))
    if flag != "一致":
        notes.append("%s 复算 %s 与报告 %s 差 %s" % (name, _fmt(computed, f), _fmt(report, f), _fmt(diff, f)))


def main():
    ap = argparse.ArgumentParser(description="混凝土重力坝坝基面应力复核（SL 319-2018 6.3）")
    ap.add_argument("--mode", required=True, choices=["base", "allow"],
                    help="base=坝基面垂直应力复算；allow=按极限强度反算容许应力")
    ap.add_argument("--w", type=float, default=None, help="ΣW：全部荷载（含扬压力）法向合力，kN（单位坝长）")
    ap.add_argument("--b", type=float, default=None, help="坝基截面宽度 B，m")
    ap.add_argument("--xr", type=float, default=None,
                    help="合力作用点至上游面的距离，m（不是偏心距，避免正负号歧义）")
    ap.add_argument("--stage", default="operation", choices=["operation", "construction"],
                    help="operation=运用期；construction=施工期")
    ap.add_argument("--combo", default="basic", choices=["basic", "special1", "special2"],
                    help="荷载组合（决定抗压安全系数限值）")
    ap.add_argument("--seismic", default=None, choices=["quasi", "dynamic"],
                    help="[可选] 地震工况：quasi=拟静力法；dynamic=动力法")
    ap.add_argument("--allow-concrete", type=float, default=None, help="[可选] 坝体混凝土容许压应力，MPa")
    ap.add_argument("--allow-rock", type=float, default=None, help="[可选] 基岩容许承载力，MPa")
    ap.add_argument("--fc", type=float, default=None, help="[可选] 大坝混凝土设计龄期极限抗压强度，MPa")
    ap.add_argument("--ft", type=float, default=None, help="[可选] 混凝土极限抗拉强度，MPa")
    ap.add_argument("--sigma-u", type=float, default=None, help="[可选] 报告给出的坝踵应力，MPa")
    ap.add_argument("--sigma-d", type=float, default=None, help="[可选] 报告给出的坝趾应力，MPa")
    ap.add_argument("--tol", type=float, default=None, help="[可选] 三方比对允许偏差，默认 0.02MPa")
    args = ap.parse_args()

    bad, notes = [], []
    rc = 0

    if args.mode == "allow":
        print("=" * 64)
        print("依据               : SL 319-2018 6.3.10（★强条）")
        if args.fc is None:
            print("★ 输入错：allow 模式需给 --fc（设计龄期极限抗压强度，MPa）")
            return 2
        if args.seismic == "quasi":
            kc, kt = K_QUASI_COMP, K_QUASI_TENS
        elif args.seismic == "dynamic":
            kc, kt = K_DYN_COMP, K_DYN_TENS
        elif args.combo == "basic":
            kc, kt = K_COMP_BASIC, K_TENSILE
        else:
            kc, kt = K_COMP_SPECIAL, K_TENSILE
        print("混凝土极限抗压强度 : %.2f MPa" % args.fc)
        print("抗压安全系数取用   : %.2f" % kc)
        print("容许压应力         : %.3f MPa" % (args.fc / kc))
        if args.ft is not None:
            print("容许拉应力         : %.3f MPa  （极限抗拉 %.2f / %.2f）" % (args.ft / kt, args.ft, kt))
        return 0

    # —— base ——
    print("=" * 64)
    print("依据               : SL 319-2018 6.3.2 / 6.3.3（★强条）/ 6.3.10（★强条）")
    print("计算阶段           : %s" % ("运用期" if args.stage == "operation" else "施工期"))
    if args.w is None or args.b is None or args.xr is None:
        print("★ 输入错：base 模式需给 --w / --b / --xr")
        return 2
    if args.b <= 0:
        print("★ 输入错：--b 应大于 0")
        return 2
    if not (0 < args.xr < args.b):
        print("★ 输入错：--xr 应在 (0, B) 内 —— 你给的是 xr=%.3f、B=%.3f" % (args.xr, args.b))
        return 2

    a = args.b * 1.0                 # 单位坝长，m2
    e_down = args.xr - args.b / 2.0  # 合力相对形心向下游的偏心距，m
    sig_u = args.w / a * (1 - 6 * e_down / args.b) / 1000.0   # kPa → MPa
    sig_d = args.w / a * (1 + 6 * e_down / args.b) / 1000.0

    print("ΣW（含扬压力）     : %.1f kN/m" % args.w)
    print("坝底宽 B           : %.2f m" % args.b)
    print("合力作用点 xr      : %.2f m（距上游面）→ 偏心距 e=%.3f m（向下游为正）" % (args.xr, e_down))
    print("复算               : 坝踵 σu = ΣW/A·(1−6e/B) = %.3f MPa" % sig_u)
    print("                    坝趾 σd = ΣW/A·(1+6e/B) = %.3f MPa" % sig_d)
    if abs(e_down) > args.b / 6.0:
        print("▲ 提示：|e| > B/6 = %.2f m，截面出现拉应力区（合力超出三分点）" % (args.b / 6.0))

    if args.stage == "operation":
        # 6.3.3 1 款：坝踵不出现拉应力（强条）
        _check_min("坝踵垂直应力(不出现拉)", sig_u, 0.0, bad, note="6.3.3-1")
        # 6.3.3 1 款：坝趾 ≤ 混凝土容许压应力 且 ≤ 基岩容许承载力
        if args.allow_concrete is not None:
            _check_max("坝趾 vs 混凝土容许压应力", sig_d, args.allow_concrete, bad, note="6.3.3-1")
        if args.allow_rock is not None:
            _check_max("坝趾 vs 基岩容许承载力", sig_d, args.allow_rock, bad, note="6.3.3-1")
        # 6.3.10：抗压安全系数
        if args.fc is not None and sig_d > 0:
            kc = args.fc / sig_d
            if args.seismic == "quasi":
                lim = K_QUASI_COMP
            elif args.seismic == "dynamic":
                lim = K_DYN_COMP
            else:
                lim = K_COMP_BASIC if args.combo == "basic" else K_COMP_SPECIAL
            _check_min("抗压安全系数 Kc=fc/σd", kc, lim, bad, note="6.3.10")
        _compare_report("坝踵应力 σu", sig_u, args.sigma_u, args.tol, notes)
        _compare_report("坝趾应力 σd", sig_d, args.sigma_d, args.tol, notes)
    else:
        # 6.3.3 2 款：施工期坝趾允许 <0.1MPa 拉应力
        _check_min("坝趾应力 ≥ −0.1MPa", sig_d, -TENSILE_CONSTRUCTION, bad, note="6.3.3-2")
        if sig_d < 0:
            print("  说明：施工期坝趾为拉应力 %.3f MPa，允许但须 <0.1MPa" % abs(sig_d))

    print("=" * 64)
    if notes:
        print("▲ 三方比对提示：%s" % "；".join(notes))
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足")
    return rc


if __name__ == "__main__":
    sys.exit(main())
