#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""防波堤 / 护岸顶高程 + 护面块体稳定重量 复算（水运工程报告审查用）。

【它解决什么】
    报告写"堤顶高程 8.50m""护面块体 4.0t"，本工具按 JTS 154—2018 与 JTS 165—2025 复算：
    ① 堤顶/护岸顶高程 = 设计高水位 + k·H（k 随结构型式与越浪要求变，0.6/0.7/0.8/1.0/1.25）；
    ② 护面块体稳定重量按 Hudson 型公式 + 表4.3.7 的 KD。
    常见错：把"允许越浪"的 0.6H 套到"基本不越浪"的堤上；KD 用块石的 4.0 去算扭王字块。

【依据】
    JTS 165—2025  5.7.9     斜坡式防波堤堤顶高程：允许越浪无胸墙 0.6H；块石/四脚空心方块/
                             栅栏板护面 0.7H；基本不越浪及宽肩台抛石 1.0H；设胸墙胸墙顶 >1.0H
    JTS 165—2025  5.7.10    重力式直立堤：允许越浪 0.6H（削角 0.7H）；基本不越浪 1.0H（削角 1.25H）
    JTS 165—2025  5.7.12    设计波浪重现期 50 年（重要建筑物 100 年）；
                             斜坡堤波列累积频率 13%，直立堤 1%
    JTS 154—2018  4.2.2     斜坡堤堤顶高程（与 5.7.9 同口径）
    JTS 154—2018  7.2.2.1   斜坡式护岸允许越浪无胸墙：岸顶高程不宜低于设计高水位以上 0.8H，
                             并应高于极端高水位；内河护岸按最高通航水位/极端高水位加 0.1~0.5m
    JTS 154—2018  8.2.8.1   直立式护岸允许越浪：顶高程可定在设计高水位以上不低于 0.7H，
                             并应高于极端高水位
    JTS 154—2018  4.3.7     护面块体稳定重量 W = 0.1·γb·H³ / [KD·(γb/γw − 1)³·cotα]
                             表4.3.7 稳定系数 KD

⚠ 4.3.7 的公式本体在 docx 中是图形对象（文本层只剩 "W＝０. １"），本实现按规范通行
  Hudson 形式落地；**引用前须与原版 4.3.7 公式核对**，故 armor 模式在无 --report 时 rc=3。

【用法】
    python calc_breakwater.py --mode crest --type slope --revetment block --zw 3.50 --h 3.0 --report 6.20
    python calc_breakwater.py --mode crest --type upright --chamfer --overtopping no --zw 3.50 --h 3.0
    python calc_breakwater.py --mode armor --armor accropode --h 3.0 --slope 2.0 --gb 24 --kd 15
    python calc_breakwater.py --mode armor --armor rock --h 2.2 --slope 2.5 --report 3.5

【退出码】0 满足 / 1 不满足 / 2 输入错 / 3 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 堤顶/护岸顶高程系数 k（顶高程 = 设计高水位 + k·H）——
K_CREST = {
    ("slope", "yes", "none"): 0.6,        # 斜坡堤 允许越浪 无胸墙
    ("slope", "yes", "block"): 0.7,       # 斜坡堤 允许越浪 块石/四脚空心方块/栅栏板
    ("slope", "no", "none"): 1.0,         # 斜坡堤 基本不越浪（含宽肩台抛石）
    ("slope", "no", "wall"): 1.0,         # 斜坡堤 基本不越浪 设胸墙（胸墙顶 >1.0H）
    ("upright", "yes", "none"): 0.6,      # 直立堤 允许越浪
    ("upright", "yes", "chamfer"): 0.7,   # 直立堤 允许越浪 削角
    ("upright", "no", "none"): 1.0,       # 直立堤 基本不越浪
    ("upright", "no", "chamfer"): 1.25,   # 直立堤 基本不越浪 削角
}
REVETMENT_K = {"slope": 0.8, "upright": 0.7}   # JTS 154 7.2.2.1 / 8.2.8.1（允许越浪）

# —— 表4.3.7 稳定系数 KD ——
KD_TABLE = {
    "rock2": ("块石·抛填2层", 4.0),
    "rock1": ("块石·安放1层", 5.5),
    "tetrapod": ("四脚锥体·随机安放2层", 8.5),
    "hollow": ("四脚空心方块·规则安放1层", 14.0),
    "dolos": ("扭工字块体·随机安放2层", 15.0),
    "accropode": ("扭王字块体·随机安放1层", 15.0),
}
KD_RANGE_NOTE = "扭工字/扭王字 KD 表列 15~18，取小值偏安全（表4.3.7 注②）"


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
    ap = argparse.ArgumentParser(description="防波堤/护岸顶高程与护面块体稳定重量复算（JTS 154 / JTS 165）")
    ap.add_argument("--mode", required=True, choices=["crest", "armor"])
    ap.add_argument("--type", default="slope", choices=["slope", "upright"], help="[crest] 结构型式")
    ap.add_argument("--revetment", action="store_true", help="[crest] 按护岸（JTS 154 7.2.2/8.2.8）而非防波堤")
    ap.add_argument("--overtopping", default="yes", choices=["yes", "no"], help="[crest] 是否允许越浪")
    ap.add_argument("--face", default="none", choices=["none", "block", "wall", "chamfer"],
                    help="[crest] 护面/胸墙/削角：none/block/wall/chamfer")
    ap.add_argument("--zw", type=float, default=None, help="[crest] 设计高水位，m")
    ap.add_argument("--ehwl", type=float, default=None, help="[crest] 极端高水位，m（护岸强制高于此值）")
    ap.add_argument("--h", type=float, default=None, help="[crest/armor] 设计波高 H，m")
    ap.add_argument("--armor", default="rock2", choices=list(KD_TABLE), help="[armor] 护面块体类型")
    ap.add_argument("--kd", type=float, default=None, help="[armor] 直接给定 KD（覆盖表值）")
    ap.add_argument("--slope", type=float, default=2.0, help="[armor] 斜坡坡率 cotα（1:m 的 m）")
    ap.add_argument("--gb", type=float, default=24.0, help="[armor] 块体材料重度 γb，kN/m³")
    ap.add_argument("--gw", type=float, default=10.25, help="[armor] 水重度 γw，kN/m³（海水10.25）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告结论值（高程 m / 块体重量 t）")
    args = ap.parse_args()

    bad, calc = [], None

    if args.mode == "crest":
        if args.zw is None or args.h is None:
            print("★ 输入错：--zw 设计高水位与 --h 设计波高必填", file=sys.stderr)
            return 2
        if args.revetment:
            k = REVETMENT_K[args.type]
            src = "JTS 154—2018 %s（允许越浪）" % ("7.2.2.1" if args.type == "slope" else "8.2.8.1")
        else:
            key = (args.type, args.overtopping, args.face)
            if key not in K_CREST:
                print("★ 输入错：组合 type=%s overtopping=%s face=%s 无对应条款"
                      % (args.type, args.overtopping, args.face), file=sys.stderr)
                return 2
            k = K_CREST[key]
            src = "JTS 165—2025 %s" % ("5.7.9" if args.type == "slope" else "5.7.10")
        calc = args.zw + k * args.h
        print("=" * 64)
        print("依据            : %s" % src)
        print("结构型式        : %s%s" % (
            "斜坡式" if args.type == "slope" else "直立式",
            "（护岸）" if args.revetment else "（防波堤）"))
        print("越浪要求        : %s" % ("允许越浪" if args.overtopping == "yes" else "基本不越浪"))
        print("设计高水位      : %.2f m" % args.zw)
        print("设计波高   H    : %.2f m" % args.h)
        print("-" * 64)
        print("高程系数   k    : %.2f H" % k)
        print("顶高程（计算）  : %.2f m  = %.2f + %.2f×%.2f" % (calc, args.zw, k, args.h))
        if args.revetment and args.ehwl is not None:
            ok = calc >= args.ehwl - 1e-9
            print("极端高水位      : %.2f m" % args.ehwl)
            if not ok:
                print("  ★ 顶高程 %.2f m 低于极端高水位 %.2f m（%s “并应高于极端高水位”为硬要求）"
                      % (calc, args.ehwl, src))
                bad.append("顶高程 %.2f < 极端高水位 %.2f" % (calc, args.ehwl))
            else:
                print("  ✓ 已高于极端高水位 %.2f m" % args.ehwl)

    else:  # armor
        if args.h is None:
            print("★ 输入错：--h 设计波高必填", file=sys.stderr)
            return 2
        name, kd_tab = KD_TABLE[args.armor]
        kd = args.kd if args.kd else kd_tab
        sr = args.gb / args.gw
        if sr <= 1.0:
            print("★ 输入错：γb/γw = %.2f ≤ 1，块体不会下沉，参数有误" % sr, file=sys.stderr)
            return 2
        w = 0.1 * args.gb * args.h ** 3 / (kd * (sr - 1) ** 3 * args.slope)
        calc = w
        print("=" * 64)
        print("依据            : JTS 154—2018 4.3.7 + 表4.3.7")
        print("护面型式        : %s" % name)
        print("稳定系数   KD   : %.1f%s" % (kd, "（报告给定）" if args.kd else ""))
        print("设计波高   H    : %.2f m" % args.h)
        print("坡率  cotα      : %.2f" % args.slope)
        print("重度  γb / γw   : %.1f / %.2f kN/m³（相对重度 %.2f）" % (args.gb, args.gw, sr))
        print("-" * 64)
        print("稳定重量   W    : %.2f t  = 0.1×%.0f×%.1f³ / [%.1f×(%.2f−1)³×%.2f]"
              % (w, args.gb, args.h, kd, sr, args.slope))
        print("  ▲ 说明：公式本体在 docx 中为图形对象，本值按 Hudson 通形式复算，须与原版 4.3.7 核对")
        if args.armor in ("dolos", "accropode") and not args.kd:
            print("  ▲ 说明：%s" % KD_RANGE_NOTE)

    if args.report is not None and calc is not None:
        print("-" * 64)
        print("报告值          : %s" % _fmt(args.report))
        print("复算值 − 报告值 : %+.2f" % (calc - args.report))
        _check_min("报告值 vs 复算值", args.report, calc, bad,
                   note="顶高程/块体重量不得小于复算值")

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    if args.mode == "armor" and args.report is None:
        print("判定：仅参考值（公式本体为图形，未与原版逐字核对，不作硬判定）")
        return 3
    print("判定：满足（复算值 %s）" % _fmt(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
