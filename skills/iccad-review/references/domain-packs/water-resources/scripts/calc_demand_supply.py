#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""供需平衡复算器 —— 核"可供 vs 需水 / 定额反算 / 生态流量"（水资源论证报告审查用）。

【它解决什么】
    报告写"供需基本平衡"却拿不出算式，或定额与需水量对不上（定额 480 m³/亩 × 35 万亩
    应得 1.68 亿 m³，报告却写 1.2 亿，中间差的就是灌溉水利用系数）——这类"数对不上"
    靠人眼翻表很难发现。本工具按"定额 × 规模 ÷ 利用系数"独立反算，再与报告值比对。

【依据】
    GB/T 35580-2017 7.3.4  现状水平年不同来水情况下的水资源供需平衡分析，评价紧缺程度
    GB/T 35580-2017 8.2.7  农业灌溉按 GB/T 50363 分析灌水技术与灌溉制度合理性
    GB/T 35580-2017 8.5.3  结合输水过程损失，核定项目总用水量
    GB/T 35580-2017 9.3.1.5 需水预测应包括河道内生态需水量
    GB/T 35580-2017 10.4.2 分析取水对生态流量（水位）的影响
    GB/T 35580-2017 9.1.2  满足河道内最小流量或水量要求

【口径】
    灌溉：W净 = 定额(m³/亩) × 面积(万亩) / 1e4        （亿m³）
          W毛 = W净 / η灌溉水利用系数
    工业：W = 定额(m³/万元) × 产值(万元) / 1e8         （亿m³）
    生活：W = 定额(L/(人·d)) × 人口(万人) × 天数 / 1e11 （亿m³）
    供需：缺口 = 需水 − 可供；保证程度 = 可供 / 需水
    生态：取水后剩余 = 多年平均流量 − 取水流量，须 ≥ 生态流量

【用法】
    python calc_demand_supply.py --mode supply --demand 1.35 --supply 1.20 --p 75
    python calc_demand_supply.py --mode supply --demand 1.35 --supply 1.20 --backup
    python calc_demand_supply.py --mode quota --kind 灌溉 --quota 480 --area 35 --eta 0.60 --report 1.20
    python calc_demand_supply.py --mode quota --kind 工业 --quota 25 --output 480000
    python calc_demand_supply.py --mode eco --mean-flow 12.0 --withdrawal 1.8

【退出码】统一语义（家族约定，勿改）
    0 = 满足
    1 = 不满足（有缺口未落实替代水源 / 定额与需水对不上 / 挤占生态流量）
    2 = 输入错
    3 = 仅参考值（信息不足）

【判据方向纪律】
    · 可供水量 ≥ 需水量 —— 下限型（缺口 = 需 − 供 ≤ 0 才成立）；
    · 取水后剩余流量 ≥ 生态流量 —— 下限型；
    · 定额反算与报告值 —— 偏差超容差即"数对不上"，属错情。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _f(v, nd=3):
    return "-" if v is None else ("%%.%df" % nd) % v


def main():
    ap = argparse.ArgumentParser(description="水资源论证 · 供需平衡与定额复算")
    ap.add_argument("--mode", required=True, choices=["supply", "quota", "eco"])
    # supply
    ap.add_argument("--demand", type=float, default=None, help="需水量（亿m³）")
    ap.add_argument("--supply", type=float, default=None, help="可供水量（亿m³）")
    ap.add_argument("--p", type=float, default=None, help="保证率（%%），如 50/75/95")
    ap.add_argument("--backup", action="store_true", help="已落实替代水源/节水措施（缺口可接受）")
    # quota
    ap.add_argument("--kind", default="灌溉", choices=["灌溉", "工业", "生活"])
    ap.add_argument("--quota", type=float, default=None, help="用水定额")
    ap.add_argument("--area", type=float, default=None, help="灌溉面积（万亩）")
    ap.add_argument("--output", type=float, default=None, help="工业产值（万元）")
    ap.add_argument("--pop", type=float, default=None, help="人口（万人）")
    ap.add_argument("--days", type=float, default=365.0, help="供水天数（默认 365）")
    ap.add_argument("--eta", type=float, default=1.0, help="水利用系数（灌溉填 η，工业/生活一般 1.0）")
    # eco
    ap.add_argument("--mean-flow", type=float, default=None, help="多年平均流量（m³/s）")
    ap.add_argument("--withdrawal", type=float, default=None, help="取水流量（m³/s）")
    ap.add_argument("--eco-flow", type=float, default=None, help="给定的生态流量（m³/s）")
    # 通用
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的对应结论值")
    ap.add_argument("--tol", type=float, default=0.05, help="相对容差（默认 0.05）")
    args = ap.parse_args()

    bad = []
    rc = 0

    if args.mode == "supply":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 7.3.4 / 8.5.3 / 9.3.1.5")
        print("口径 : 缺口 = 需水 − 可供；保证程度 = 可供 / 需水")
        print("-" * 66)
        if args.demand is None or args.supply is None:
            print("★ 输入错：supply 模式须给 --demand 与 --supply")
            return 2
        if args.demand <= 0:
            bad.append("需水量 ≤ 0（%s）" % _f(args.demand))
        gap = args.demand - args.supply
        rate = args.supply / args.demand * 100.0 if args.demand else 0.0
        print("  需水量 W需           : %s 亿m³%s" % (
            _f(args.demand), ("（P=%g%%）" % args.p) if args.p is not None else ""))
        print("  可供水量 W供         : %s 亿m³" % _f(args.supply))
        print("  → 缺口               : %s 亿m³" % _f(gap))
        print("  → 保证程度           : %.1f%%" % rate)
        print("-" * 66)
        if gap > 1e-9:
            if args.backup:
                print("  缺口 %s 亿m³ —— 报告已提出替代水源/节水措施，**须核其是否落实到位**" % _f(gap))
            else:
                print("  缺口 %s 亿m³ —— 未落实替代水源，供需不平衡" % _f(gap))
                bad.append("供需缺口 %s 亿m³（可供 %s < 需水 %s），未论证替代水源"
                           % (_f(gap), _f(args.supply), _f(args.demand)))
        else:
            print("  可供水量覆盖需水量，余量 %s 亿m³" % _f(-gap))
        if args.report is not None:
            dev = abs(gap - args.report) / max(abs(args.report), 1e-9) if args.report else abs(gap)
            ok = dev <= args.tol
            print("报告缺口             : %s ｜偏差 %.2f%%  %s" % (
                _f(args.report), dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("缺口复算 %s vs 报告 %s" % (_f(gap), _f(args.report)))

    elif args.mode == "quota":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 8.2.7（灌溉制度）+ 8.5.3（核定总用水量）")
        print("-" * 66)
        if args.quota is None:
            print("★ 输入错：quota 模式须给 --quota")
            return 2
        if args.eta <= 0:
            print("★ 输入错：--eta 必须 > 0")
            return 2
        net = None
        if args.kind == "灌溉":
            if args.area is None:
                print("★ 输入错：灌溉须给 --area（万亩）")
                return 2
            net = args.quota * args.area / 1e4
            print("  灌溉定额             : %s m³/亩" % _f(args.quota, 0))
            print("  灌溉面积             : %s 万亩" % _f(args.area, 2))
            print("  → 净需水量 W净       : %s 亿m³  [定额×面积/1e4]" % _f(net))
        elif args.kind == "工业":
            if args.output is None:
                print("★ 输入错：工业须给 --output（万元）")
                return 2
            net = args.quota * args.output / 1e8
            print("  工业用水定额         : %s m³/万元" % _f(args.quota, 2))
            print("  产值                 : %s 万元" % _f(args.output, 0))
            print("  → 需水量 W           : %s 亿m³  [定额×产值/1e8]" % _f(net))
        else:  # 生活
            if args.pop is None:
                print("★ 输入错：生活须给 --pop（万人）")
                return 2
            net = args.quota * args.pop * 1e4 * args.days / 1e11
            print("  生活用水定额         : %s L/(人·d)" % _f(args.quota, 0))
            print("  人口                 : %s 万人" % _f(args.pop, 2))
            print("  供水天数             : %s d" % _f(args.days, 0))
            print("  → 需水量 W           : %s 亿m³  [定额×人口×天数/1e11]" % _f(net))

        gross = net / args.eta
        print("-" * 66)
        print("  水利用系数 η         : %.3f" % args.eta)
        print("  → 毛需水量 W毛       : %s 亿m³  [W净 / η]" % _f(gross))
        print("     灌溉口径：η = 渠系水利用系数 × 田间水利用系数（大型灌区常 0.55~0.65）")
        print("     工业/生活口径：定额若已为取水定额，η 取 1.0")
        if args.eta > 1.0:
            bad.append("水利用系数 %.3f > 1（不可能，须 ≤ 1）" % args.eta)
        if args.report is not None:
            # 两种情况都判：报告值可能对应净需水，也可能对应毛取水
            matched = False
            for label, ref in (("净需水", net), ("毛需水", gross)):
                if ref and abs(args.report - ref) / abs(ref) <= args.tol:
                    print("  报告值 %s 与%s %s 一致（偏差 %.2f%%）" % (
                        _f(args.report), label, _f(ref), abs(args.report - ref) / abs(ref) * 100.0))
                    matched = True
                    break
            if not matched:
                bad.append("报告水量 %s 与反算净需水 %s / 毛需水 %s 均不符（η=%.2f）"
                           % (_f(args.report), _f(net), _f(gross), args.eta))
                print("  ★ 报告值 %s 与净 %s、毛 %s 都对不上 —— 定额、面积或利用系数必有一项错"
                      % (_f(args.report), _f(net), _f(gross)))

    elif args.mode == "eco":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 9.1.2 / 10.4.2（生态流量与最小下泄流量）")
        print("口径 : 取水后剩余 = 多年平均流量 − 取水流量 ≥ 生态流量")
        print("-" * 66)
        if args.mean_flow is None or args.withdrawal is None:
            print("★ 输入错：eco 模式须给 --mean-flow 与 --withdrawal")
            return 2
        left = args.mean_flow - args.withdrawal
        print("  多年平均流量 Q均     : %s m³/s" % _f(args.mean_flow))
        print("  取水流量 Q取         : %s m³/s" % _f(args.withdrawal))
        print("  → 取水后剩余 Q剩     : %s m³/s" % _f(left))
        if args.mean_flow > 0:
            print("  → 取水占多年平均     : %.1f%%" % (args.withdrawal / args.mean_flow * 100.0))
        print("-" * 66)
        # Tennant 参考线（非规范硬判据，仅作量级提示）
        t10 = args.mean_flow * 0.10
        t30 = args.mean_flow * 0.30
        print("  Tennant 参考：10%% = %s m³/s（最小）；30%% = %s m³/s（良好）"
              % (_f(t10), _f(t30)))
        if args.eco_flow is not None:
            ok = left >= args.eco_flow - 1e-9
            print("  给定生态流量 Q生     : %s m³/s  %s  取水后剩余 %s  %s" % (
                _f(args.eco_flow), "≤" if ok else "★>", _f(left), "满足" if ok else "**挤占**"))
            if not ok:
                bad.append("取水后剩余 %s < 生态流量 %s（挤占 %s m³/s）"
                           % (_f(left), _f(args.eco_flow), _f(args.eco_flow - left)))
        else:
            if left < t10:
                bad.append("取水后剩余 %s < 多年平均的 10%%（%s），已低于 Tennant 最小生态流量参考线"
                           % (_f(left), _f(t10)))
            elif left < t30:
                print("  ⚠ 取水后剩余低于 30% 参考线，属生态偏紧区间，须核报告是否给出生态流量论证")
            if left <= 0:
                bad.append("取水后剩余 ≤ 0（%s），河道断流" % _f(left))
        if args.report is not None:
            dev = abs(left - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= args.tol
            print("报告剩余流量         : %s ｜偏差 %.2f%%  %s" % (
                _f(args.report), dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("取水后剩余流量复算 %s vs 报告 %s" % (_f(left), _f(args.report)))

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
