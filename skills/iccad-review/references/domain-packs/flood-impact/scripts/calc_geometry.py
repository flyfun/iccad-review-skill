#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""涉河项目几何关系校核 —— 夹角 / 承台顶高程 / 跨堤梁底高程。

【判定依据】SL/T 808-2025
    5.2.2-2  桥梁轴线宜与河道主流方向垂直；桥墩顺水流方向轴线应与中高洪水时主流方向一致，
             确实难以满足的，夹角不应大于 5°（与 JTG D60-2015 3.2.3 一致）
    5.2.5    桥墩承台顶高程不应高于规划河底高程，不宜高于冲刷线高程；墩头宜圆型或流线型
    5.2.2-5  宜立交跨越堤防；确需平交的，跨堤部分梁底高程应高于规划堤顶高程，
             不应削弱堤身设计断面，并做防渗加固；两侧宜设长度不小于桥面宽度的水平连接段
    5.3.2-4  盾构/顶管工作井、隧道进出口、通风口高程要求（辅助校核）

【模式】
  angle       桥墩轴线与中高洪水主流方向夹角（≤5°）
  cap-elev    桥墩承台顶高程 vs 规划河底高程 / 冲刷线高程
  cross-dike  跨堤梁底高程 vs 规划堤顶高程（+ 水平连接段长度）

【用法】
  python calc_geometry.py --mode angle --angle 6.5
  python calc_geometry.py --mode cap-elev --cap-elev 3.20 --river-bed-elev 3.50 --scour-elev 2.80
  python calc_geometry.py --mode cross-dike --beam-elev 13.60 --dike-crest-elev 13.40 \
         --conn-length 26 --bridge-width 24

【退出码】0 = 满足；1 = 不满足（含"应/不应"级别不满足）；2 = 输入错误
"""
import argparse
import sys

ANGLE_LIMIT = 5.0   # 5.2.2-2 夹角上限（°）


def main():
    ap = argparse.ArgumentParser(description="涉河项目几何关系校核（SL/T 808-2025）")
    ap.add_argument("--mode", required=True, choices=["angle", "cap-elev", "cross-dike"])
    ap.add_argument("--angle", type=float, default=None, help="[angle] 桥墩轴线与主流方向夹角 (°)")
    ap.add_argument("--cap-elev", type=float, default=None, help="[cap-elev] 承台顶高程 (m)")
    ap.add_argument("--river-bed-elev", type=float, default=None, help="[cap-elev] 规划河底高程 (m)")
    ap.add_argument("--scour-elev", type=float, default=None, help="[cap-elev] [可选] 冲刷线高程 (m)")
    ap.add_argument("--beam-elev", type=float, default=None, help="[cross-dike] 跨堤部分梁底高程 (m)")
    ap.add_argument("--dike-crest-elev", type=float, default=None, help="[cross-dike] 规划堤顶高程 (m)")
    ap.add_argument("--conn-length", type=float, default=None, help="[cross-dike] [可选] 水平连接段长度 (m)")
    ap.add_argument("--bridge-width", type=float, default=None, help="[cross-dike] [可选] 桥面宽度 (m)")
    args = ap.parse_args()

    print("=" * 60)
    print("几何关系校核（SL/T 808-2025）")
    print("=" * 60)
    bad = []
    warn = []

    if args.mode == "angle":
        if args.angle is None:
            print("输入错误：angle 需 --angle", file=sys.stderr)
            return 2
        a = abs(args.angle)
        print("依据               : SL/T 808-2025 5.2.2-2（与 JTG D60-2015 3.2.3 一致）")
        print("要求               : 桥梁轴线宜与主流垂直；桥墩轴线宜与中高洪水主流方向一致，"
              "难以满足时夹角 ≤ %.0f°" % ANGLE_LIMIT)
        print("报告交角           : %.2f°" % a)
        if a <= ANGLE_LIMIT + 1e-9:
            print("  判定：满足")
        else:
            print("  ★ 判定：不满足 —— 夹角 %.2f° > %.0f°，须专门论证并说明减缓措施"
                  % (a, ANGLE_LIMIT))
            bad.append("桥墩轴线与主流夹角 %.2f° > %.0f°" % (a, ANGLE_LIMIT))

    elif args.mode == "cap-elev":
        if args.cap_elev is None or args.river_bed_elev is None:
            print("输入错误：cap-elev 需 --cap-elev --river-bed-elev", file=sys.stderr)
            return 2
        print("依据               : SL/T 808-2025 5.2.5")
        print("承台顶高程         : %.2f m" % args.cap_elev)
        print("规划河底高程       : %.2f m" % args.river_bed_elev)
        if args.cap_elev <= args.river_bed_elev + 1e-9:
            print("  判定（不应高于规划河底）：满足")
        else:
            print("  ★ 判定（不应高于规划河底）：不满足 —— 高出 %.2f m"
                  % (args.cap_elev - args.river_bed_elev))
            bad.append("承台顶高程 %.2f m 高于规划河底 %.2f m"
                       % (args.cap_elev, args.river_bed_elev))
        if args.scour_elev is not None:
            print("-" * 60)
            print("冲刷线高程         : %.2f m" % args.scour_elev)
            if args.cap_elev <= args.scour_elev + 1e-9:
                print("  判定（不宜高于冲刷线）：满足")
            else:
                print("  ▲ 提示（不宜高于冲刷线）：承台顶高出冲刷线 %.2f m —— 属'不宜'条款，"
                      "须说明理由并评估局部冲刷影响（不单独构成硬错情）"
                      % (args.cap_elev - args.scour_elev))
                warn.append("承台顶高程 %.2f m 高于冲刷线 %.2f m（不宜）"
                            % (args.cap_elev, args.scour_elev))

    else:  # cross-dike
        if args.beam_elev is None or args.dike_crest_elev is None:
            print("输入错误：cross-dike 需 --beam-elev --dike-crest-elev", file=sys.stderr)
            return 2
        print("依据               : SL/T 808-2025 5.2.2-5")
        print("跨堤部分梁底高程   : %.2f m" % args.beam_elev)
        print("规划堤顶高程       : %.2f m" % args.dike_crest_elev)
        if args.beam_elev + 1e-9 >= args.dike_crest_elev:
            print("  判定（应高于规划堤顶）：满足")
        else:
            print("  ★ 判定（应高于规划堤顶）：不满足 —— 低于 %.2f m"
                  % (args.dike_crest_elev - args.beam_elev))
            bad.append("跨堤梁底高程 %.2f m 低于规划堤顶 %.2f m"
                       % (args.beam_elev, args.dike_crest_elev))
        if args.conn_length is not None and args.bridge_width is not None:
            print("-" * 60)
            print("水平连接段长度     : %.1f m    桥面宽度 : %.1f m" % (args.conn_length, args.bridge_width))
            if args.conn_length + 1e-9 >= args.bridge_width:
                print("  判定（宜 ≥ 桥面宽度）：满足")
            else:
                print("  ▲ 提示（宜 ≥ 桥面宽度）：连接段短 %.1f m —— 属'宜'条款，须说明"
                      % (args.bridge_width - args.conn_length))
                warn.append("水平连接段长度 %.1f m < 桥面宽度 %.1f m（宜）"
                            % (args.conn_length, args.bridge_width))

    print("-" * 60)
    if bad:
        print("★ 结论：不满足 —— " + "；".join(bad))
        rc = 1
    else:
        print("结论：满足（就本次给定值而言）")
        rc = 0
    if warn:
        print("▲ 另有 %d 项'宜'级提示（不构成硬错情）：%s" % (len(warn), "；".join(warn)))
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
