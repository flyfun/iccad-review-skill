#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桥涵设计洪水频率 / 涵洞净高 / 导流堤判据 复核 —— 涉河桥梁、涵洞类项目。

【判定依据】JTG D60-2015《公路桥涵设计通用规范》
    表 3.2.9  桥涵设计洪水频率
    3.4.4     无压力式涵洞内顶点至最高流水面的净高
    3.2.8-4   单边河滩流量不超过总流量 15% 或双边河滩流量不超过 25% 时，可不设导流堤
  配合：SL/T 808-2025 5.2.2-6（梁底最低高程应满足防洪要求）、5.2.3（相邻桥梁间距应大于壅水长度）

【⚠ 重要提示】JTG D60-2015 **不在技能自带条文库**（见 references/norms.md §三），
  本册数值取自该规范正文，**输出一律带"待核"标记**，正式成果须与 JTG D60-2015 原规范核对。

【模式】
  freq        桥涵设计洪水频率（表 3.2.9）
  culvert     无压力式涵洞内顶点至最高流水面净高（3.4.4）
  beach-flow  河滩流量占比 → 是否可不设导流堤（3.2.8-4）

【用法】
  python calc_bridge.py --mode freq --road-class 高速公路 --bridge-type 特大桥 --report 300
  python calc_bridge.py --mode culvert --culvert-type 管涵/拱涵 --height 2.5 \
         --flow-level 12.30 --vertex-elev 12.85
  python calc_bridge.py --mode beach-flow --side 单边 --beach-flow 180 --total-flow 1200

【退出码】0 = 满足/可不设；1 = 不满足（频率偏低/净高不足/超阈值）；2 = 输入错误
"""
import argparse
import sys

# ---- JTG D60-2015 表 3.2.9 桥涵设计洪水频率（重现期，年）----
FREQ = {
    "高速公路": {"特大桥": 300, "大桥": 100, "中桥": 100, "小桥": 100, "涵洞": 100},
    "一级公路": {"特大桥": 300, "大桥": 100, "中桥": 100, "小桥": 100, "涵洞": 100},
    "二级公路": {"特大桥": 100, "大桥": 100, "中桥": 100, "小桥": 50,  "涵洞": 50},
    "三级公路": {"特大桥": 100, "大桥": 50,  "中桥": 50,  "小桥": 25,  "涵洞": 25},
    "四级公路": {"特大桥": 100, "大桥": 50,  "中桥": 50,  "小桥": 25,  "涵洞": None},
}

# ---- JTG D60-2015 3.4.4 无压力式涵洞净高：h≤3m 时取 h/den；h>3m 时取定值 fix (m) ----
CULVERT = {
    "管涵/拱涵": {"den": 4, "fix": 0.75, "desc": "h≤3m 取 h/4；h>3m 取 0.75"},
    "矩形涵":    {"den": 6, "fix": 0.50, "desc": "h≤3m 取 h/6；h>3m 取 0.50"},
}

# ---- JTG D60-2015 3.2.8-4 免设导流堤阈值（河滩流量 / 总流量 × 100%）----
BEACH_THRESHOLD = {"单边": 15.0, "双边": 25.0}

ROAD_ALIAS = {"高速": "高速公路", "高速公路": "高速公路",
              "一级": "一级公路", "一级公路": "一级公路",
              "二级": "二级公路", "二级公路": "二级公路",
              "三级": "三级公路", "三级公路": "三级公路",
              "四级": "四级公路", "四级公路": "四级公路"}
BTYPE_ALIAS = {"特大桥": "特大桥", "大桥": "大桥", "中桥": "中桥", "小桥": "小桥",
               "涵洞": "涵洞", "涵": "涵洞", "小型排水构造物": "涵洞"}
CULV_ALIAS = {"管涵/拱涵": "管涵/拱涵", "管涵": "管涵/拱涵", "拱涵": "管涵/拱涵",
              "圆管涵": "管涵/拱涵", "矩形涵": "矩形涵", "矩形涵洞": "矩形涵", "箱涵": "矩形涵"}


def main():
    ap = argparse.ArgumentParser(description="桥涵设计洪水频率 / 涵洞净高 / 导流堤判据 复核（JTG D60-2015）")
    ap.add_argument("--mode", required=True, choices=["freq", "culvert", "beach-flow"])
    ap.add_argument("--road-class", default=None, help="[freq] 公路等级：高速/一级/二级/三级/四级")
    ap.add_argument("--bridge-type", default=None, help="[freq] 特大桥/大桥/中桥/小桥/涵洞")
    ap.add_argument("--culvert-type", default=None, help="[culvert] 管涵/拱涵 或 矩形涵（箱涵）")
    ap.add_argument("--height", type=float, default=None, help="[culvert] 涵洞孔径/净高 h (m)")
    ap.add_argument("--flow-level", type=float, default=None, help="[culvert] 涵内最高流水面高程 (m)")
    ap.add_argument("--vertex-elev", type=float, default=None, help="[culvert] 涵洞内顶点高程 (m)")
    ap.add_argument("--side", default=None, help="[beach-flow] 单边 / 双边")
    ap.add_argument("--beach-flow", type=float, default=None, help="[beach-flow] 河滩（一侧或两侧）流量 (m³/s)")
    ap.add_argument("--total-flow", type=float, default=None, help="[beach-flow] 总流量 (m³/s)")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告取用值（频率/净高/占比），用于比对")
    args = ap.parse_args()

    print("=" * 60)
    print("桥涵复核（JTG D60-2015）")
    print("=" * 60)
    bad = []

    if args.mode == "freq":
        rc_key = ROAD_ALIAS.get(args.road_class, args.road_class)
        bt = BTYPE_ALIAS.get(args.bridge_type, args.bridge_type)
        if rc_key not in FREQ or bt not in FREQ[rc_key]:
            print("输入错误：--road-class 取 高速/一级/二级/三级/四级；--bridge-type 取 特大桥/大桥/中桥/小桥/涵洞",
                  file=sys.stderr)
            return 2
        need = FREQ[rc_key][bt]
        print("依据               : JTG D60-2015 表 3.2.9 桥涵设计洪水频率")
        print("公路等级 / 桥型    : %s / %s" % (rc_key, bt))
        if need is None:
            print("规范要求           : 不作规定（四级公路涵洞）")
        else:
            print("规范要求           : 1/%d（即 %d 年一遇）" % (need, need))
        if args.report is not None and need is not None:
            print("-" * 60)
            print("报告取用频率       : 1/%.0f（%.0f 年一遇）" % (args.report, args.report))
            if args.report + 1e-9 >= need:
                print("  判定：满足 —— 不低于表 3.2.9 要求")
            else:
                print("  ★ 判定：不满足 —— 报告频率 %.0f 年 < 要求 %d 年" % (args.report, need))
                bad.append("桥涵设计洪水频率 %.0f 年 < 要求 %d 年" % (args.report, need))
        elif need is not None:
            print("（未给 --report，仅列规范要求）")
        print("★ 待核：JTG D60-2015 未入自带条文库，表号与数值须与原规范核对。")

    elif args.mode == "culvert":
        ct = CULV_ALIAS.get(args.culvert_type, args.culvert_type)
        if ct not in CULVERT or args.height is None:
            print("输入错误：culvert 需 --culvert-type 管涵/拱涵|矩形涵 与 --height h(m)", file=sys.stderr)
            return 2
        info = CULVERT[ct]
        h = args.height
        if h <= 0:
            print("输入错误：h 须为正", file=sys.stderr)
            return 2
        need = h / info["den"] if h <= 3.0 else info["fix"]
        print("依据               : JTG D60-2015 3.4.4 无压力式涵洞内顶点至最高流水面净高")
        print("涵洞型式 / 净高 h  : %s / %.2f m" % (ct, h))
        print("取值规则           : %s" % info["desc"])
        print("要求净高           : ≥ %.3f m" % need)
        if args.vertex_elev is not None and args.flow_level is not None:
            act = args.vertex_elev - args.flow_level
            print("-" * 60)
            print("涵内最高流水面     : %.2f m" % args.flow_level)
            print("涵洞内顶点         : %.2f m" % args.vertex_elev)
            print("实际净高           : %.3f m" % act)
            if act + 1e-9 >= need:
                print("  判定：满足")
            else:
                print("  ★ 判定：不满足 —— 净高不足 %.3f m" % (need - act))
                bad.append("涵洞净高 %.3f m < 要求 %.3f m" % (act, need))
        elif args.report is not None:
            print("-" * 60)
            print("报告给出净高       : %.3f m" % args.report)
            if args.report + 1e-9 >= need:
                print("  判定：满足")
            else:
                print("  ★ 判定：不满足 —— 净高不足 %.3f m" % (need - args.report))
                bad.append("涵洞净高 %.3f m < 要求 %.3f m" % (args.report, need))
        else:
            print("（未给 --vertex-elev/--flow-level 或 --report，仅列要求）")
        print("★ 待核：JTG D60-2015 未入自带条文库，3.4.4 数值须与原规范核对。")

    else:  # beach-flow
        side = args.side
        if side not in BEACH_THRESHOLD or args.beach_flow is None or args.total_flow is None:
            print("输入错误：beach-flow 需 --side 单边/双边 --beach-flow --total-flow", file=sys.stderr)
            return 2
        if args.total_flow <= 0:
            print("输入错误：总流量须为正", file=sys.stderr)
            return 2
        ratio = args.beach_flow / args.total_flow * 100.0
        thr = BEACH_THRESHOLD[side]
        print("依据               : JTG D60-2015 3.2.8-4（导流堤设置判据）")
        print("河滩位置 / 流量    : %s / %.1f m³/s（总流量 %.1f m³/s）"
              % (side, args.beach_flow, args.total_flow))
        print("河滩流量占比       : %.2f%%    （阈值 %.0f%%）" % (ratio, thr))
        if ratio <= thr + 1e-9:
            print("  判定：可不设导流堤（在 %.0f%% 阈值以内）" % thr)
        else:
            print("  ★ 判定：超过 %.0f%% 阈值 —— 宜设置导流堤；报告未设的须说明理由" % thr)
            bad.append("河滩流量占比 %.2f%% > %.0f%% 阈值" % (ratio, thr))
        print("★ 待核：JTG D60-2015 未入自带条文库，3.2.8-4 阈值须与原规范核对。")

    print("-" * 60)
    if bad:
        print("★ 结论：不满足 —— " + "；".join(bad))
        rc = 1
    else:
        print("结论：满足（就本次给定值而言）")
        rc = 0
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
