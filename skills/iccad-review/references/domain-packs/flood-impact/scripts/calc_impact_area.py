#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""影响分析范围核定 —— 洪评报告"影响分析范围"章节的硬约束。

【判定依据】SL/T 808-2025
    表 1  影响分析范围参考取值（上游及下游河道长度）
              山区   3B
              丘陵区 (3~5)B
              平原区 (5~10)B
           注：B 为项目所在河段两堤之间的河道宽度；无堤段河道，
               以历史最高洪水位河宽计算。
    2.0.5 影响分析范围 —— 建设项目在施工、运行及管理过程中，可能对水利规划实施、
          河势稳定、河道行洪、湖泊容积、水库库容、流域防洪体系……等造成不利影响的
          空间范围。
    B.1/B.2/B.3 报告参考目录中"1.3 影响分析范围"为必备章节。

【用法】
    python calc_impact_area.py --zone 平原区 --b 320
    python calc_impact_area.py --zone 丘陵区 --b 180 --upstream 600 --downstream 700
    python calc_impact_area.py --zone 山区 --b 90 --report-total 300

【退出码】0 = 报告范围不小于参考下限；1 = 小于参考下限（偏小，须补）；2 = 输入错误
"""
import argparse
import sys

# 表 1 影响分析范围参考取值：(下限系数, 上限系数, 参考取值)
ZONE = {
    "山区":   (3.0, 3.0, "3B"),
    "丘陵区": (3.0, 5.0, "(3~5)B"),
    "平原区": (5.0, 10.0, "(5~10)B"),
}


def main():
    ap = argparse.ArgumentParser(description="影响分析范围核定（SL/T 808-2025 表1）")
    ap.add_argument("--zone", required=True, choices=sorted(ZONE), help="分区：山区/丘陵区/平原区")
    ap.add_argument("--b", type=float, required=True, help="河段两堤之间河道宽度 B (m)；无堤段取历史最高洪水位河宽")
    ap.add_argument("--upstream", type=float, default=None, help="[可选] 报告取用的上游河道长度 (m)")
    ap.add_argument("--downstream", type=float, default=None, help="[可选] 报告取用的下游河道长度 (m)")
    ap.add_argument("--report-total", type=float, default=None, help="[可选] 报告取用的影响分析范围总长 (m)")
    args = ap.parse_args()

    if args.b <= 0:
        print("输入错误：B 须为正", file=sys.stderr)
        return 2

    lo, hi, ref = ZONE[args.zone]
    req_lo, req_hi = lo * args.b, hi * args.b

    print("=" * 60)
    print("影响分析范围核定（SL/T 808-2025 表 1）")
    print("=" * 60)
    print("分区                     : %s" % args.zone)
    print("B（两堤间河宽）          : %.1f m" % args.b)
    print("参考取值                 : %s" % ref)
    print("上游及下游河道长度       : %.1f ~ %.1f m" % (req_lo, req_hi))
    if lo == hi:
        print("                          （山区固定 3B，即上下各约 %.1f m）" % req_lo)
    else:
        print("                          （即上游+下游合计约 %.1f ~ %.1f m）" % (req_lo, req_hi))

    bad = []
    if args.upstream is not None:
        ok = args.upstream + 1e-9 >= req_lo
        print("-" * 60)
        print("报告上游长度             : %.1f m   %s" % (args.upstream, "满足下限" if ok else "★ 小于下限"))
        if not ok:
            bad.append("上游 %.1f m < 下限 %.1f m" % (args.upstream, req_lo))
    if args.downstream is not None:
        ok = args.downstream + 1e-9 >= req_lo
        print("报告下游长度             : %.1f m   %s" % (args.downstream, "满足下限" if ok else "★ 小于下限"))
        if not ok:
            bad.append("下游 %.1f m < 下限 %.1f m" % (args.downstream, req_lo))
    if args.report_total is not None:
        total_req = (args.upstream or 0) and req_lo or req_lo
        print("报告影响分析范围总长     : %.1f m" % args.report_total)
        print("  注：报告总长若为上下合计，对照下限 2×(下限值) 时须注意口径；"
              "表 1 给的是'上游及下游'各自长度")

    print("-" * 60)
    if bad:
        print("★ 判定：影响分析范围偏小 —— " + "；".join(bad))
        print("  处理：按 SL/T 808-2025 表 1 扩大影响分析范围；并核对 B 的取值口径"
              "（有堤段取两堤间河宽、无堤段取历史最高洪水位河宽）。")
        rc = 1
    else:
        print("判定：影响分析范围不小于表 1 参考下限（未给报告值时不作判定）。")
        rc = 0
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
