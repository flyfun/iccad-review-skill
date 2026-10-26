#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝顶高程与防浪墙顶高程复核（混凝土重力坝报告审查用）。

【它解决什么】
    报告给出 "坝顶高程 123.50m，满足要求"，本工具按 SL 319-2018 4.2.1（★强条）
    独立复算：分别按**正常蓄水位**与**校核洪水位**算 Δh = h1% + hz + hc，
    取两者中防浪墙顶高程的**高者**，再反推坝顶高程，并校核
    "坝顶高程应高于水库最高静水位"。

【依据】
    SL 319-2018 4.2.1（★强条）：坝顶高程应高于水库最高静水位；防浪墙顶高程应高于
    波浪顶高程；Δh = h1% + hz + hc；应选择两者中防浪墙顶高程的高者作为最低高程。
    SL 319-2018 表 4.2.1 安全加高 hc：
        正常蓄水位 1级 0.7 / 2级 0.5 / 3级 0.4 m
        校核洪水位 1级 0.5 / 2级 0.4 / 3级 0.3 m
    h1%、hz 按 SL 744 计算（本工具不重算波高，只接受报告或波浪计算书给出的值）。

【用法】
    # 两个水位各算一遍（name 用 normal / check 区分，决定取哪一列安全加高）
    python calc_dam_crest.py --mode crest --grade 2 \
        --case normal,0.86,0.31,118.00 --case check,0.62,0.22,120.40 \
        --wall-h 1.2 --top 121.30

    # 只查安全加高
    python calc_dam_crest.py --mode hc --grade 1 --level normal

【退出码】统一语义（家族约定，勿改）
    0 = 满足    1 = 不满足（含违反强条）    2 = 输入错    3 = 仅参考值

【判据方向纪律】
    坝顶/防浪墙顶高程是**下限型**（越高越安全）→ 一律 _check_min。
    把"高程不够"判成满足（方向反了）是本域最严重的误判之一。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表 4.2.1 安全加高 hc（m），SL 319-2018；判据方向：取值表，非判据 ——
HC = {
    "normal": {1: 0.7, 2: 0.5, 3: 0.4},   # 正常蓄水位
    "check":  {1: 0.5, 2: 0.4, 3: 0.3},   # 校核洪水位
}
LEVEL_CN = {"normal": "正常蓄水位", "check": "校核洪水位"}


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


def _parse_case(s):
    """解析 "name,h1p,hz,zw" → (name, h1p, hz, zw)。"""
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 4:
        raise ValueError("--case 需要 4 个字段：名称,波高h1%,波浪中心线高hz,相应水位 —— 收到 %r" % s)
    name = parts[0].lower()
    if name not in HC:
        raise ValueError("--case 名称只能是 normal（正常蓄水位）或 check（校核洪水位）—— 收到 %r" % parts[0])
    return name, float(parts[1]), float(parts[2]), float(parts[3])


def main():
    ap = argparse.ArgumentParser(description="混凝土重力坝坝顶高程复核（SL 319-2018 4.2.1）")
    ap.add_argument("--mode", required=True, choices=["crest", "hc"],
                    help="crest=复算坝顶与防浪墙顶高程；hc=查表 4.2.1 安全加高")
    ap.add_argument("--grade", type=int, required=True, choices=[1, 2, 3], help="坝的级别 1/2/3")
    ap.add_argument("--level", default="normal", choices=["normal", "check"],
                    help="[hc 模式] 相应水位：normal=正常蓄水位；check=校核洪水位")
    ap.add_argument("--case", action="append", default=None,
                    help="[crest 模式] 可重复：名称(normal/check),h1%%波高,hz,相应水位")
    ap.add_argument("--wall-h", type=float, default=1.2, help="防浪墙高度，m，默认 1.2")
    ap.add_argument("--top", type=float, default=None, help="[可选] 报告给出的坝顶高程，m")
    ap.add_argument("--parapet", type=float, default=None, help="[可选] 报告给出的防浪墙顶高程，m")
    ap.add_argument("--tol", type=float, default=0.05, help="[可选] 三方比对允许偏差，m，默认 0.05")
    args = ap.parse_args()

    bad, notes = [], []

    if args.mode == "hc":
        hc = HC[args.level][args.grade]
        print("=" * 64)
        print("依据               : SL 319-2018 表 4.2.1（4.2.1 为★强条）")
        print("%s / %d 级坝       : 安全加高 hc = %.2f m" % (LEVEL_CN[args.level], args.grade, hc))
        print("说明               : hc 是查表值，不作合格判定；判定见 --mode crest")
        return 0

    if not args.case:
        print("★ 输入错：crest 模式至少给一个 --case normal,h1%,hz,水位")
        return 2
    try:
        cases = [_parse_case(s) for s in args.case]
    except ValueError as e:
        print("★ 输入错：%s" % e)
        return 2

    print("=" * 64)
    print("依据               : SL 319-2018 4.2.1（★强条）及表 4.2.1")
    print("坝的级别           : %d 级" % args.grade)
    print("防浪墙高度         : %.2f m" % args.wall_h)
    print("-" * 64)

    wall_tops = []
    for name, h1p, hz, zw in cases:
        hc = HC[name][args.grade]
        dh = h1p + hz + hc
        wt = zw + dh
        wall_tops.append((wt, name, zw))
        print("%-10s : 水位 %.3f + h1%% %.3f + hz %.3f + hc %.2f = 防浪墙顶 %.3f"
              % (LEVEL_CN[name], zw, h1p, hz, hc, wt))
        print("%-10s   Δh = %.3f m" % ("", dh))

    top_wall, top_name, _ = max(wall_tops, key=lambda x: x[0])
    max_zw = max(c[3] for c in cases)
    top_deck = top_wall - args.wall_h

    print("-" * 64)
    print("控制工况           : %s（防浪墙顶高程最高）" % LEVEL_CN[top_name])
    print("复算 防浪墙顶高程  : %.3f m" % top_wall)
    print("复算 坝顶高程      : %.3f m（防浪墙顶 − 墙高 %.2f）" % (top_deck, args.wall_h))
    print("最高静水位         : %.3f m" % max_zw)
    print("-" * 64)

    # 4.2.1 强条：坝顶高程应高于水库最高静水位
    _check_min("坝顶高程 vs 最高静水位", top_deck, max_zw, bad, note="4.2.1")
    # 防浪墙顶须高于波浪顶：即须取到两工况的高者（本工具已按 max 取，此处复核报告值）
    if args.top is not None:
        _check_min("报告坝顶高程 vs 最高静水位", args.top, max_zw, bad, note="4.2.1")
        diff = abs(args.top - top_deck)
        print("  %-30s : 复算 %s / 报告 %s / 差 %s  %s"
              % ("坝顶高程(三方比对)", _fmt(top_deck), _fmt(args.top), _fmt(diff),
                 "一致" if diff <= args.tol else "★须核对"))
        if diff > args.tol:
            notes.append("坝顶高程 复算 %.3f 与报告 %.3f 差 %.3f" % (top_deck, args.top, diff))
    if args.parapet is not None:
        diff = abs(args.parapet - top_wall)
        print("  %-30s : 复算 %s / 报告 %s / 差 %s  %s"
              % ("防浪墙顶高程(三方比对)", _fmt(top_wall), _fmt(args.parapet), _fmt(diff),
                 "一致" if diff <= args.tol else "★须核对"))
        if diff > args.tol:
            notes.append("防浪墙顶 复算 %.3f 与报告 %.3f 差 %.3f" % (top_wall, args.parapet, diff))

    print("=" * 64)
    if notes:
        print("▲ 三方比对提示：%s" % "；".join(notes))
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足")
    return 0


if __name__ == "__main__":
    sys.exit(main())
