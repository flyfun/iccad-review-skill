#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阻水比 / 行洪断面缩窄率 复算 —— 洪评报告"河道行洪影响"核心判据。

【判定依据】SL/T 808-2025
    5.2.2-3  跨河建设项目的阻水比应严格控制，**不应大于 5%**，确实难以满足的，
             应对防洪安全的影响进行专门论证。
    5.4.2-3  码头、取排水设施等构筑物阻水比**不应大于 2%**。
    6.4.2    占用行洪断面的建设项目，应计算总阻水比及**河槽、滩地阻水比**、
             占用行洪面积。
    7.5.2    据各工况壅水高度及范围、流量变化、阻水比、占用行洪面积，
             分析对河道行洪和排涝能力的影响。

【阻水比定义】
    总阻水比 = 阻水面积 / 设计洪水位下全断面过水面积 × 100%
    河槽阻水比 = 河槽内阻水面积 / 河槽过水面积 × 100%
    滩地阻水比 = 滩地内阻水面积 / 滩地过水面积 × 100%

【用法】
    # 跨河桥梁（阈值 5%）
    python calc_blockage.py --type cross-river --a-block 6.2 --a-total 140
    # 临河码头（阈值 2%），带河槽/滩地分算
    python calc_blockage.py --type riverside --a-block 3.0 --a-total 300 \\
        --a-channel 120 --a-channel-block 0.4 --a-beach 180 --a-beach-block 2.6
    # 比对报告给出的阻水比，并算行洪断面缩窄率
    python calc_blockage.py --type cross-river --a-block 6.2 --a-total 140 \\
        --b1 60 --b2 57 --report 4.4

【退出码】0 = 满足；1 = 超限（不满足）；2 = 输入错误
"""
import argparse
import sys

# 阻水比限值（SL/T 808-2025 5.2.2-3 / 5.4.2-3）
LIMIT = {
    "cross-river": (5.0, "SL/T 808-2025  5.2.2-3  跨河建设项目阻水比不应大于 5%"),
    "bridge": (5.0, "SL/T 808-2025  5.2.2-3  跨河建设项目阻水比不应大于 5%"),
    "pipe": (5.0, "SL/T 808-2025  5.2.2-3  跨河建设项目阻水比不应大于 5%"),
    "cable": (5.0, "SL/T 808-2025  5.2.2-3  跨河建设项目阻水比不应大于 5%"),
    "riverside": (2.0, "SL/T 808-2025  5.4.2-3  码头、取排水设施等构筑物阻水比不应大于 2%"),
    "wharf": (2.0, "SL/T 808-2025  5.4.2-3  码头、取排水设施等构筑物阻水比不应大于 2%"),
    "intake": (2.0, "SL/T 808-2025  5.4.2-3  码头、取排水设施等构筑物阻水比不应大于 2%"),
    "outfall": (2.0, "SL/T 808-2025  5.4.2-3  码头、取排水设施等构筑物阻水比不应大于 2%"),
}


def pct(a, b):
    return None if (b is None or b <= 0) else 100.0 * a / b


def main():
    ap = argparse.ArgumentParser(description="阻水比 / 行洪断面缩窄率 复算（SL/T 808-2025）")
    ap.add_argument("--type", required=True,
                    choices=sorted(LIMIT),
                    help="项目类别：cross-river/bridge/pipe/cable（阈值5%%）/ riverside/wharf/intake/outfall（阈值2%%）")
    ap.add_argument("--a-block", type=float, required=True, help="阻水面积 (m²)")
    ap.add_argument("--a-total", type=float, required=True, help="设计洪水位下全断面过水面积 (m²)")
    ap.add_argument("--a-channel", type=float, default=None, help="[可选] 河槽过水面积 (m²)")
    ap.add_argument("--a-channel-block", type=float, default=None, help="[可选] 河槽内阻水面积 (m²)")
    ap.add_argument("--a-beach", type=float, default=None, help="[可选] 滩地过水面积 (m²)")
    ap.add_argument("--a-beach-block", type=float, default=None, help="[可选] 滩地内阻水面积 (m²)")
    ap.add_argument("--b1", type=float, default=None, help="[可选] 原行洪断面宽度 (m)")
    ap.add_argument("--b2", type=float, default=None, help="[可选] 缩窄后行洪断面宽度 (m)")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的阻水比 (%%)，用于比对")
    ap.add_argument("--limit", type=float, default=None, help="[可选] 覆盖默认限值 (%%)")
    args = ap.parse_args()

    if args.a_total <= 0 or args.a_block < 0:
        print("输入错误：过水面积须为正、阻水面积不得为负", file=sys.stderr)
        return 2
    if args.a_block > args.a_total:
        print("输入错误：阻水面积大于过水面积，请核对取值", file=sys.stderr)
        return 2

    limit, ref = LIMIT[args.type]
    if args.limit is not None:
        limit, ref = args.limit, "审查人指定限值 %.2f%%" % args.limit

    total = pct(args.a_block, args.a_total)
    chan = pct(args.a_channel_block, args.a_channel) if (args.a_channel_block is not None and args.a_channel) else None
    beach = pct(args.a_beach_block, args.a_beach) if (args.a_beach_block is not None and args.a_beach) else None
    narrow = None
    if args.b1 and args.b2 is not None and args.b1 > 0:
        narrow = 100.0 * (args.b1 - args.b2) / args.b1

    print("=" * 60)
    print("阻水比复核（SL/T 808-2025）")
    print("=" * 60)
    print("项目类别           : %s" % args.type)
    print("复算总阻水比       : %.2f%%   （阻水面积 %.1f m² / 过水面积 %.1f m²）"
          % (total, args.a_block, args.a_total))
    if chan is not None:
        print("复算河槽阻水比     : %.2f%%   （%.2f m² / %.1f m²）"
              % (chan, args.a_channel_block, args.a_channel))
    if beach is not None:
        print("复算滩地阻水比     : %.2f%%   （%.2f m² / %.1f m²）"
              % (beach, args.a_beach_block, args.a_beach))
    if narrow is not None:
        print("行洪断面缩窄率     : %.2f%%   （B₁=%.1f m → B₂=%.1f m）" % (narrow, args.b1, args.b2))
    print("适用限值           : ≤ %.2f%%" % limit)
    print("依据               : %s" % ref)

    if args.report is not None:
        dev = total - args.report
        print("-" * 60)
        print("报告给出阻水比     : %.2f%%" % args.report)
        print("复算 − 报告        : %+.2f 个百分点" % dev)
        if abs(dev) > 0.3:
            print("★ 偏差 > 0.3 个百分点 —— 须核对阻水面积取值口径（是否含基础、围堰、"
                  "施工期临时结构）或过水断面切取位置")

    print("-" * 60)
    ok = total <= limit + 1e-9
    # 分项也应各自不超过限值
    sub_over = [("%s阻水比" % n, v) for n, v in (("河槽", chan), ("滩地", beach)) if v is not None and v > limit + 1e-9]
    if ok and not sub_over:
        print("判定：满足  —— 阻水比 %.2f%% ≤ %.2f%%" % (total, limit))
    else:
        why = []
        if not ok:
            why.append("总阻水比 %.2f%% > %.2f%%" % (total, limit))
        for n, v in sub_over:
            why.append("%s %.2f%% > %.2f%%" % (n, v, limit))
        print("★ 判定：不满足 —— " + "；".join(why))
        print("  处理：按 SL/T 808-2025 5.2.2-3，确实难以满足的应对防洪安全影响"
              "进行专门论证；或优化布置减少阻水（减少支墩/一跨跨越/后移支墩）。")
    print("=" * 60)
    return 0 if (ok and not sub_over) else 1


if __name__ == "__main__":
    sys.exit(main())
