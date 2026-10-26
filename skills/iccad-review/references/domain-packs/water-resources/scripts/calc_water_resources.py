#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水资源量复算器 —— 核"总量扣重 / 可利用量 / 开发利用程度"（水资源论证报告审查用）。

【它解决什么】
    "地表水 + 地下水 = 水资源总量"是本域最典型、也最常见的一处硬错：
    地表水与地下水之间存在**相互转化的重复计算量**，直接相加会把总量算虚高。
    另一个高频错是把"开发利用程度"的分子分母口径搞错（地表水拿地下水的可开采量做分母）。
    本工具按 7.2 / 表1 注1 的口径独立复算，并做"复算 / 报告"三方比对。

【依据】
    GB/T 35580-2017 7.2.2  简述水资源数量、质量、时空分布、水资源可利用量
    GB/T 35580-2017 表1 注1 开发利用程度 = 多年平均地表水资源供水量 / 地表水资源量；
                            或 多年平均地下水资源供水量 / 地下水可开采量
    GB/T 35580-2017 7.3.4  现状水平年不同来水情况下的水资源供需平衡分析
    GB/T 35580-2017 7.4.1  按用水总量控制、用水效率控制、限制纳污要求分析开发利用潜力
    ★ 注意：**GB/T 35580 本身没有"重复计算量"这一条**。扣重公式来自"水资源总量"的
      通用定义（《水资源评价导则》SL/T 238 与《水资源公报》口径一致）：
      总量 = 地表 + 地下 − 重复。引用时按"水资源总量定义"标注，**不要写成 GB/T 35580 某条**。

【口径（务必与报告核对一致）】
    水资源总量 W总 = W地表 + W地下 − W重复
        W重复：地表水与地下水相互转化的重复计算量（含河川基流、渠系渗漏补给等）
    可利用量 W可利用 = W总 − W生态 − W汛期弃水（或由报告直接给出可利用率）
    开发利用程度 η = W供 / W资源   ×100%
        地表水：W资源 = 地表水资源量
        地下水：W资源 = 地下水可开采量

【用法】
    python calc_water_resources.py --mode total --surface 1.60 --ground 0.28 --repeat 0.10 --report 1.88
    python calc_water_resources.py --mode availability --total 1.78 --eco 0.20 --flood-reject 0.15 --withdrawal 1.20
    python calc_water_resources.py --mode exploit --supply 4.50 --resource 6.25 --kind 地表
    python calc_water_resources.py --mode exploit --supply 0.80 --resource 1.20 --kind 地下 --report 72

【退出码】统一语义（家族约定，勿改）
    0 = 满足
    1 = 不满足（漏扣重复量 / 超可利用量 / 与报告显著不符）
    2 = 输入错
    3 = 仅参考值（信息不足）

【判据方向纪律】
    本域两类：
      · 恒等式（总量扣重）→ 偏差超容差即不满足；
      · 上限型（取水量 vs 可利用量）→ 取水量 ≤ 可利用量，超过即不满足。
    "开发利用程度"是**分级指标**，不作对错判定，只按表1 给出等级。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表1 取水水源分类指标（开发利用程度，%）——
#   方向：数值越大等级越高（越严）。边界归属：≥一级阈值 → 一级；≥二级阈值 → 二级；其余三级
DEV_LIMIT = {
    "地表": {"一级": 30.0, "二级": 10.0},
    "地下": {"一级": 70.0, "二级": 50.0},
}


def _f(v, nd=3):
    return "-" if v is None else ("%%.%df" % nd) % v


def _grade(kind, pct):
    """按表1 判定开发利用程度等级。"""
    lim = DEV_LIMIT[kind]
    if pct >= lim["一级"]:
        return "一级"
    if pct >= lim["二级"]:
        return "二级"
    return "三级"


def main():
    ap = argparse.ArgumentParser(description="水资源论证 · 水资源量与开发程度复算")
    ap.add_argument("--mode", required=True, choices=["total", "availability", "exploit"])
    # total
    ap.add_argument("--surface", type=float, default=None, help="地表水资源量（亿m³）")
    ap.add_argument("--ground", type=float, default=None, help="地下水资源量（亿m³）")
    ap.add_argument("--repeat", type=float, default=None, help="重复计算量（亿m³）")
    # availability
    ap.add_argument("--total", type=float, default=None, help="水资源总量（亿m³）")
    ap.add_argument("--eco", type=float, default=None, help="河道内生态需水量（亿m³）")
    ap.add_argument("--flood-reject", type=float, default=None, help="汛期弃水/不可控水量（亿m³）")
    ap.add_argument("--withdrawal", type=float, default=None, help="拟取水量（亿m³）")
    # exploit
    ap.add_argument("--supply", type=float, default=None, help="供水量（亿m³）")
    ap.add_argument("--resource", type=float, default=None,
                    help="分母：地表=地表水资源量；地下=地下水可开采量（亿m³）")
    ap.add_argument("--kind", default="地表", choices=["地表", "地下"])
    # 通用
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的对应结论值")
    ap.add_argument("--tol", type=float, default=0.02, help="相对容差（默认 0.02）")
    args = ap.parse_args()

    bad = []
    rc = 0

    if args.mode == "total":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 7.2.2（水资源数量）+ 水资源总量定义")
        print("口径 : W总 = W地表 + W地下 − W重复")
        print("-" * 66)
        if args.surface is None or args.ground is None:
            print("★ 输入错：total 模式须给 --surface 与 --ground")
            return 2
        repeat = args.repeat if args.repeat is not None else 0.0
        if args.repeat is None:
            print("  ⚠ 未给 --repeat，按 0 计 —— 若报告也未扣重复量，这正是要抓的错")
        total = args.surface + args.ground - repeat
        naive = args.surface + args.ground
        print("  地表水资源量 W地表 : %s 亿m³" % _f(args.surface))
        print("  地下水资源量 W地下 : %s 亿m³" % _f(args.ground))
        print("  重复计算量   W重复 : %s 亿m³" % _f(repeat))
        print("  → 水资源总量 W总   : %s 亿m³" % _f(total))
        if repeat > 0:
            print("  （若不扣重复量会虚高 %s 亿m³，相对虚高 %.1f%%）"
                  % (_f(repeat), repeat / total * 100.0 if total else 0))
        print("-" * 66)
        if total <= 0:
            bad.append("水资源总量 ≤ 0（%s），量纲或数值填错" % _f(total))
        if repeat < 0:
            bad.append("重复计算量为负（%s）" % _f(repeat))
        if repeat > 0 and args.surface and args.ground and repeat > min(args.surface, args.ground):
            print("  ⚠ 重复量大于任一水源量，须核对（通常不会超过较小者）")
        if args.report is not None:
            dev = abs(total - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= args.tol
            print("报告总量 : %s 亿m³ ｜偏差 %.2f%%  %s" % (
                _f(args.report), dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                # 精确诊断：报告是否等于"未扣重复"的直加值
                if abs(args.report - naive) <= max(args.tol * naive, 1e-9):
                    bad.append("报告总量 %s = 地表+地下直加值 %s，**漏扣重复计算量 %s**"
                               % (_f(args.report), _f(naive), _f(repeat)))
                else:
                    bad.append("报告总量 %s 与复算 %s 偏差 %.2f%%"
                               % (_f(args.report), _f(total), dev * 100.0))

    elif args.mode == "availability":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 7.2.2（水资源可利用量）+ 7.3.4（供需平衡）")
        print("口径 : W可利用 = W总 − W生态 − W汛期弃水")
        print("-" * 66)
        if args.total is None:
            print("★ 输入错：availability 模式须给 --total")
            return 2
        eco = args.eco or 0.0
        rej = args.flood_reject or 0.0
        avail = args.total - eco - rej
        print("  水资源总量 W总       : %s 亿m³" % _f(args.total))
        print("  河道内生态需水 W生态 : %s 亿m³" % _f(eco))
        print("  汛期弃水/不可控 W弃  : %s 亿m³" % _f(rej))
        print("  → 可利用量 W可利用   : %s 亿m³" % _f(avail))
        if args.total:
            print("  → 可利用率           : %.1f%%" % (avail / args.total * 100.0))
        print("-" * 66)
        if avail <= 0:
            bad.append("可利用量 ≤ 0（%s），生态/弃水取值过大或总量偏小" % _f(avail))
        if args.withdrawal is not None:
            ok = args.withdrawal <= avail + 1e-9
            print("  拟取水量 W取         : %s 亿m³  %s 可利用量 %s  %s" % (
                _f(args.withdrawal), "≤" if ok else "★>", _f(avail), "满足" if ok else "**超出**"))
            if not ok:
                bad.append("拟取水量 %s > 可利用量 %s（超出 %s）" % (
                    _f(args.withdrawal), _f(avail), _f(args.withdrawal - avail)))
            if avail > 0:
                print("  取水占可利用量比例   : %.1f%%" % (args.withdrawal / avail * 100.0))
        if args.report is not None:
            dev = abs(avail - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= args.tol
            print("报告可利用量         : %s ｜偏差 %.2f%%  %s" % (
                _f(args.report), dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("可利用量复算 %s vs 报告 %s" % (_f(avail), _f(args.report)))

    elif args.mode == "exploit":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 表1 注1（开发利用程度定义与分级）")
        print("口径 : η = W供 / W资源 ×100%%；分母 %s" % (
            "地表水资源量" if args.kind == "地表" else "地下水可开采量"))
        print("-" * 66)
        if args.supply is None or not args.resource:
            print("★ 输入错：exploit 模式须给 --supply 与 --resource（非 0）")
            return 2
        pct = args.supply / args.resource * 100.0
        g = _grade(args.kind, pct)
        print("  水源类型             : %s" % args.kind)
        print("  供水量 W供           : %s 亿m³" % _f(args.supply))
        print("  分母 W资源           : %s 亿m³" % _f(args.resource))
        print("  → 开发利用程度 η     : %.1f%%" % pct)
        print("  → 按表1 分类等级     : %s" % g)
        lim = DEV_LIMIT[args.kind]
        print("     （%s：≥%.0f%% 一级；%.0f%%~%.0f%% 二级；<%.0f%% 三级）"
              % (args.kind, lim["一级"], lim["二级"], lim["一级"], lim["二级"]))
        if pct > 100:
            bad.append("开发利用程度 %.1f%% > 100%%（供水量已超资源量，须核对口径或属超采）" % pct)
        if args.kind == "地下" and pct > 100:
            print("  ⚠ 地下水供水量超可开采量 → 超采，须核查是否位于地下水超采区（7.2.5 / 9.2.6）")
        if args.report is not None:
            dev = abs(pct - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= max(args.tol, 0.01)
            print("报告值               : %.1f%% ｜偏差 %.2f%%  %s" % (
                args.report, dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("开发利用程度复算 %.1f%% vs 报告 %.1f%%" % (pct, args.report))

    print("=" * 66)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    if rc == 3:
        print("判定：参考（信息不足，未做硬判定）")
        return 3
    print("判定：满足")
    return 0


if __name__ == "__main__":
    sys.exit(main())
