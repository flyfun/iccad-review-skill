#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""壅水高度 / 壅水曲线长度 复算 —— 洪评报告"河道行洪影响"核心判据。

【判定依据】SL/T 808-2025 附录 A.2（壅水分析计算）
    A.2.1  壅水分析计算可选用经验公式计算法、水面曲线计算法。
    A.2.3  桥梁等阻水建筑物壅水高度及壅水曲线长度，宜参照 TB 10017 按式(A.2.3-1)：
               ΔZ_M = η ( V_M² − V² )
           式中 ΔZ_M — 桥前最大壅水高度 (m)；
                η    — 系数，按表 A.2.3-1 取值；
                V    — 断面平均流速，为设计流量被全河过水断面(包括河滩)除得之商 (m/s)；
                V_M  — 桥下平均流速 (m/s)，按表 A.2.3-2 的规定求得。
           壅水曲线全长 L_Y ≈ 2 ΔZ_M / I₀（I₀ 为河段天然水面坡度）。
    5.2.3  同一河段相邻桥梁间距应大于桥梁壅水长度。

【表 A.2.3-1  η 系数】按"河滩路堤阻挡的流量与设计流量比值"分档：
    河滩很小的山区河流      ≤10%   → η = 0.05
    河滩较小的半山区河流    11~30% → η = 0.07
    有中等河滩的平原河流    31~50% → η = 0.10
    河滩较大的低洼区河流    >50%   → η = 0.15

【V_M 怎么取】三选一（按可用资料）：
    --vm  直接给（报告通常给出桥下平均流速）；
    --p   给冲刷系数 P，按 V_M = V / P 反算（P = 桥下实际过水面积 / 桥下设计过水面积）；
    --vp  给设计流速 V_P 与 --p 联用。
    注：表 A.2.3-2 只给"土质→颗粒直径"的分类，V_M 的具体数值须由冲刷系数或
        实测/模型成果确定，故本工具不替用户猜 V_M。

【用法】
    # 已知桥下平均流速
    python calc_backwater.py --v 1.8 --vm 1.35 --ratio 15 --i0 0.0004
    # 已知冲刷系数
    python calc_backwater.py --v 1.8 --p 1.33 --char plain
    # 直接给 η，并与报告值比对
    python calc_backwater.py --v 1.8 --vm 1.35 --eta 0.07 --report 0.12

【退出码】0 = 正常输出；1 = 与报告值显著不符（>0.05m），提示复核；2 = 输入错误
"""
import argparse
import sys

# 表 A.2.3-1 η 系数
ETA_TABLE = [
    ("山区",     "河滩很小的山区河流",    10.0, 0.05),
    ("半山区",   "河滩较小的半山区河流",  30.0, 0.07),
    ("平原",     "有中等河滩的平原河流",  50.0, 0.10),
    ("低洼区",   "河滩较大的低洼区河流", float("inf"), 0.15),
]
CHAR_ALIAS = {
    "山区": "山区", "mountain": "山区",
    "半山区": "半山区", "semi": "半山区",
    "平原": "平原", "plain": "平原",
    "低洼区": "低洼区", "low": "低洼区", "低洼": "低洼区",
}


def eta_from_ratio(ratio):
    """按河滩路堤阻挡流量与设计流量比值(%)查表 A.2.3-1。"""
    for key, name, ub, val in ETA_TABLE:
        if ratio <= ub:
            return val, name
    return 0.15, "河滩较大的低洼区河流"


def eta_from_char(ch):
    k = CHAR_ALIAS.get(ch)
    for key, name, ub, val in ETA_TABLE:
        if key == k:
            return val, name
    return None, None


def main():
    ap = argparse.ArgumentParser(description="壅水高度 / 壅水曲线长 复算（SL/T 808-2025 附录 A.2）")
    ap.add_argument("--v", type=float, required=True, help="断面平均流速 V (m/s)，=设计流量/全河过水断面")
    ap.add_argument("--vm", type=float, default=None, help="桥下平均流速 V_M (m/s)")
    ap.add_argument("--p", type=float, default=None, help="冲刷系数 P（V_M = V/P）")
    ap.add_argument("--vp", type=float, default=None, help="[可选] 设计流速 V_P；给了则 V_M = V_P/P")
    ap.add_argument("--eta", type=float, default=None, help="η 系数（直接给，优先于查表）")
    ap.add_argument("--ratio", type=float, default=None, help="河滩路堤阻挡流量/设计流量 (%%)，用于查表")
    ap.add_argument("--char", default=None, help="河流特征：山区/半山区/平原/低洼区（用于查表，取该档下限侧的保守值）")
    ap.add_argument("--i0", type=float, default=None, help="[可选] 天然水面坡度 I₀（用于算壅水曲线长）")
    ap.add_argument("--spacing", type=float, default=None, help="[可选] 相邻桥梁实际间距 (m)，用于核 5.2.3")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的壅水高度 (m)")
    ap.add_argument("--ly", type=float, default=None,
                    help="[可选] 报告给出的壅水长度 (m)；给了则据其判定 5.2.3（比近似式可靠）")
    args = ap.parse_args()

    if args.v <= 0:
        print("输入错误：V 须为正", file=sys.stderr)
        return 2

    # 定 V_M
    vm = args.vm
    vm_src = "直接给定"
    if vm is None:
        if args.p and args.p > 0:
            base = args.vp if args.vp else args.v
            vm = base / args.p
            vm_src = "V_M = %s / P = %.4f / %.3f" % ("V_P" if args.vp else "V", base, args.p)
        else:
            print("输入错误：须给 --vm，或给 --p（配合 --v / --vp）以反算 V_M", file=sys.stderr)
            return 2

    # 定 η
    if args.eta is not None:
        eta, eta_src = args.eta, "直接给定"
    elif args.ratio is not None:
        eta, name = eta_from_ratio(args.ratio)
        eta_src = "查表 A.2.3-1（阻挡流量比 %.1f%% → %s）" % (args.ratio, name)
    elif args.char is not None:
        eta, name = eta_from_char(args.char)
        if eta is None:
            print("输入错误：--char 取值须为 山区/半山区/平原/低洼区", file=sys.stderr)
            return 2
        eta_src = "查表 A.2.3-1（%s）" % name
    else:
        print("输入错误：须给 --eta，或给 --ratio / --char 以查表", file=sys.stderr)
        return 2

    dz_raw = eta * (vm ** 2 - args.v ** 2)
    dz = max(dz_raw, 0.0)

    print("=" * 60)
    print("壅水复算（SL/T 808-2025 附录 A.2.3）")
    print("=" * 60)
    print("断面平均流速 V      : %.4f m/s" % args.v)
    print("桥下平均流速 V_M    : %.4f m/s   [%s]" % (vm, vm_src))
    print("η 系数              : %.3f         [%s]" % (eta, eta_src))
    print("ΔZ_M = η(V_M²−V²)   : %.4f m" % dz_raw)
    if dz_raw < 0:
        print("  ⚠ V_M < V 得负值——通常意味着桥孔扩大了过水断面或取值有误；已按 0 计。")
    print("桥前最大壅水高度    : %.3f m" % dz)

    ly = None
    if args.i0:
        if args.i0 <= 0:
            print("输入错误：I₀ 须为正", file=sys.stderr)
            return 2
        ly = 2.0 * dz / args.i0
        print("壅水曲线全长 L_Y    : %.1f m   （= 2ΔZ_M / I₀，I₀=%.5f）" % (ly, args.i0))
        print("  ⚠ 式(A.2.3-4)公式本体为图片，本工具按行业通用近似式 L≈2ΔZ/I₀ 还原，")
        print("    L_Y 仅作量级参考，正式成果以报告附录计算书/水面曲线法为准。")

    if args.report is not None:
        dev = dz - args.report
        print("-" * 60)
        print("报告给出壅水高度    : %.3f m" % args.report)
        print("复算 − 报告         : %+.4f m" % dev)

    bad = []
    ly_use, ly_src = None, None
    if args.ly is not None:
        ly_use, ly_src = args.ly, "报告给出的壅水长度"
    elif ly is not None:
        ly_use, ly_src = ly, "本工具近似式 2ΔZ_M/I₀（仅供量级参考）"
    if args.spacing is not None and ly_use is not None:
        print("-" * 60)
        print("相邻桥梁实际间距    : %.1f m" % args.spacing)
        print("对照壅水长度 L_Y    : %.1f m   [%s]" % (ly_use, ly_src))
        if args.spacing > ly_use:
            print("判定(5.2.3)：满足 —— 间距 %.1f m > 壅水长度 %.1f m" % (args.spacing, ly_use))
        elif args.ly is not None:
            print("★ 判定(5.2.3)：不满足 —— 间距 %.1f m ≤ 壅水长度 %.1f m，"
                  "须按数值模拟/河工模型分析工程群累积效应" % (args.spacing, ly_use))
            bad.append("相邻桥梁间距 %.1f m ≤ 壅水长度 %.1f m（违反 5.2.3）" % (args.spacing, ly_use))
        else:
            print("▲ 提示(5.2.3)：间距 ≤ 近似壅水长度 —— 但 L_Y 系本工具按通用近似式还原，"
                  "**不作硬判定**；请用报告给出的壅水长度经 --ly 传入后再判，或按数值模拟/河工模型分析。")
    elif args.spacing is not None:
        print("-" * 60)
        print("（判定 5.2.3 需给 --ly（报告壅水长度）或 --i0（天然水面坡度）以求得 L_Y）")

    print("=" * 60)
    if args.report is not None and abs(dz - args.report) > 0.05:
        print("★ 复算与报告差 > 0.05 m —— 须核对 V、V_M、η 三者的取值与来源。")
        bad.append("复算壅水 %.3f m 与报告 %.3f m 相差 > 0.05 m" % (dz, args.report))
    if bad:
        print("★ 结论：不满足 —— " + "；".join(bad))
        return 1
    print("结论：满足（就本次给定值而言）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
