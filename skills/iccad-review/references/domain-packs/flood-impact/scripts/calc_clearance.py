#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""桥下最小净空 / 拱脚淹没 / 水库区净空 / 调治构造物超高 复核。

【判定依据】SL/T 808-2025 表 2（非通航河流桥下最小净空），与
    《公路桥涵设计通用规范》JTG D60-2015 表 3.4.3 一致：
        桥梁部位      情况                高出计算水位/m   高出最高流冰面/m
        梁底         洪水期无大漂流物      0.50            0.75
        梁底         洪水期有大漂流物      1.50            —
        梁底         有泥石流              1.00            —
        支承垫石顶面                       0.25            0.50
        有铰拱拱脚                         0.25            0.25
    另（JTG D60-2015）：
        3.4.3-4 无铰拱的拱脚允许被设计洪水淹没，但不宜超过拱圈高度的 2/3，
                且拱顶底面至计算水位的净高不得小于 1.0 m。
        3.4.3-5 在不通航和无流筏的水库区域内，梁底面或无铰拱拱顶底面离开水面的
                高度不应小于计算浪高的 0.75 倍加上 0.25 m。
        3.2.8-2 非淹没式调治构造物顶面，应高出桥涵设计洪水频率的水位至少 0.25 m。

【配合条文】SL/T 808-2025
    5.2.2-6 跨河建设项目梁底最低高程应满足防洪要求，并保障流冰、泥石流、
            漂浮物等障碍物顺利通过。
    5.5.3-2 蓄滞洪区桥梁梁底应高于设计蓄洪水位，并留有一定安全超高，
            且应满足水上救生要求。
    5.5.5-2 蓄滞洪区架空敷设管道，架空结构底部应高于设计蓄洪水位。

【模式】
    table      按表 2 复核梁底/垫石/拱脚净空
    arch       无铰拱拱脚淹没深度 + 拱顶净高（1.0 m 底线）
    reservoir  水库区净空（0.75×浪高 + 0.25 m）
    dike       调治构造物顶面超高（≥ 设计洪水位 + 0.25 m）

【用法】
    python calc_clearance.py --mode table --part 梁底 --case 无大漂流物 --water-level 12.30 --struct-elev 12.86
    python calc_clearance.py --mode arch --water-level 12.30 --arch-foot-elev 11.90 --arch-top-elev 14.10
    python calc_clearance.py --mode reservoir --wave-height 0.8 --water-level 20.0 --struct-elev 20.9
    python calc_clearance.py --mode dike --design-flood-level 12.30 --struct-elev 12.60

【退出码】0 = 满足；1 = 不满足（净空不足/淹没超限）；2 = 输入错误
"""
import argparse
import sys

# 表 2 非通航河流桥下最小净空： (计算水位净空, 最高流冰面净空)
T2 = {
    ("梁底", "无大漂流物"): (0.50, 0.75),
    ("梁底", "有大漂流物"): (1.50, None),
    ("梁底", "有泥石流"):   (1.00, None),
    ("支承垫石顶面", None): (0.25, 0.50),
    ("有铰拱拱脚", None):   (0.25, 0.25),
}
ALIAS = {
    "梁底": "梁底", "梁": "梁底",
    "支承垫石顶面": "支承垫石顶面", "垫石": "支承垫石顶面", "支承垫石": "支承垫石顶面",
    "有铰拱拱脚": "有铰拱拱脚", "拱脚": "有铰拱拱脚",
    "无大漂流物": "无大漂流物", "有大漂流物": "有大漂流物", "有泥石流": "有泥石流",
}


def _ali(v):
    return ALIAS.get(v, v) if v else None


def main():
    ap = argparse.ArgumentParser(description="桥下净空 / 拱脚淹没 / 水库区净空 / 构造物超高 复核")
    ap.add_argument("--mode", required=True, choices=["table", "arch", "reservoir", "dike"])
    ap.add_argument("--part", default=None, help="[table] 梁底 / 支承垫石顶面 / 有铰拱拱脚")
    ap.add_argument("--case", default=None, help="[table] 无大漂流物 / 有大漂流物 / 有泥石流（梁底必填）")
    ap.add_argument("--water-level", type=float, default=None, help="计算水位 / 设计洪水位 / 设计蓄洪水位 (m)")
    ap.add_argument("--struct-elev", type=float, default=None, help="梁底 / 垫石顶面 / 拱脚 / 架空结构底部 / 构造物顶面高程 (m)")
    ap.add_argument("--ice-elev", type=float, default=None, help="[可选] 最高流冰面高程 (m)")
    ap.add_argument("--arch-foot-elev", type=float, default=None, help="[arch] 拱脚高程 (m)")
    ap.add_argument("--arch-top-elev", type=float, default=None, help="[arch] 拱顶底面高程 (m)")
    ap.add_argument("--wave-height", type=float, default=None, help="[reservoir] 计算浪高 (m)")
    ap.add_argument("--design-flood-level", type=float, default=None, help="[dike] 设计洪水位 (m)")
    args = ap.parse_args()

    print("=" * 60)
    print("净空 / 淹没复核（SL/T 808-2025 表2，引 JTG D60-2015）")
    print("=" * 60)
    bad = []

    if args.mode == "table":
        part = _ali(args.part)
        case = _ali(args.case)
        if part is None or args.water_level is None or args.struct_elev is None:
            print("输入错误：table 需 --part --water-level --struct-elev", file=sys.stderr)
            return 2
        if part == "梁底" and case is None:
            print("输入错误：梁底须指定 --case（无大漂流物/有大漂流物/有泥石流）", file=sys.stderr)
            return 2
        key = (part, case) if part == "梁底" else (part, None)
        if key not in T2:
            print("输入错误：部件/情况组合不在表 2 中：%s / %s" % (part, case), file=sys.stderr)
            return 2
        need_w, need_ice = T2[key]
        actual = args.struct_elev - args.water_level
        print("部位 / 情况        : %s %s" % (part, ("/ " + case) if case else ""))
        print("计算水位           : %.2f m" % args.water_level)
        print("%s高程            : %.2f m" % (part, args.struct_elev))
        print("实际净空           : %.2f m    （高出计算水位）" % actual)
        print("表 2 要求          : ≥ %.2f m" % need_w)
        if actual + 1e-9 >= need_w:
            print("  判定：满足")
        else:
            print("  ★ 判定：不满足 —— 净空不足 %.2f m" % (need_w - actual))
            bad.append("净空 %.2f m < 要求 %.2f m" % (actual, need_w))
        if need_ice is not None and args.ice_elev is not None:
            act_ice = args.struct_elev - args.ice_elev
            print("-" * 60)
            print("最高流冰面         : %.2f m" % args.ice_elev)
            print("高出最高流冰面     : %.2f m    （要求 ≥ %.2f m）" % (act_ice, need_ice))
            if act_ice + 1e-9 < need_ice:
                print("  ★ 判定：不满足 —— 流冰面净空不足 %.2f m" % (need_ice - act_ice))
                bad.append("流冰面净空 %.2f m < 要求 %.2f m" % (act_ice, need_ice))
            else:
                print("  判定：满足")
        print("依据               : SL/T 808-2025 表 2 / JTG D60-2015 表 3.4.3")
    elif args.mode == "arch":
        for k in ("water_level", "arch_foot_elev", "arch_top_elev"):
            if getattr(args, k) is None:
                print("输入错误：arch 需 --water-level --arch-foot-elev --arch-top-elev", file=sys.stderr)
                return 2
        arch_h = args.arch_top_elev - args.arch_foot_elev
        if arch_h <= 0:
            print("输入错误：拱圈高度须为正", file=sys.stderr)
            return 2
        sub = args.water_level - args.arch_foot_elev
        sub = max(sub, 0.0)
        net_top = args.arch_top_elev - args.water_level
        print("拱圈高度           : %.2f m" % arch_h)
        print("拱脚被淹深度       : %.2f m    （限值 ≤ 2/3×拱高 = %.2f m）" % (sub, 2.0 * arch_h / 3.0))
        if sub <= 2.0 * arch_h / 3.0 + 1e-9:
            print("  判定：满足")
        else:
            print("  ★ 判定：不满足 —— 拱脚淹没超过拱圈高度 2/3")
            bad.append("拱脚淹没 %.2f m > 2/3×拱高 %.2f m" % (sub, 2.0 * arch_h / 3.0))
        print("拱顶底面至计算水位净高: %.2f m  （要求 ≥ 1.00 m）" % net_top)
        if net_top + 1e-9 >= 1.0:
            print("  判定：满足")
        else:
            print("  ★ 判定：不满足 —— 拱顶净高不足")
            bad.append("拱顶净高 %.2f m < 1.00 m" % net_top)
        print("依据               : JTG D60-2015 3.4.3-4")
    elif args.mode == "reservoir":
        for k in ("wave_height", "water_level", "struct_elev"):
            if getattr(args, k) is None:
                print("输入错误：reservoir 需 --wave-height --water-level --struct-elev", file=sys.stderr)
                return 2
        need = 0.75 * args.wave_height + 0.25
        actual = args.struct_elev - args.water_level
        print("计算浪高           : %.2f m" % args.wave_height)
        print("要求净空           : 0.75×%.2f + 0.25 = %.3f m" % (args.wave_height, need))
        print("实际净空           : %.3f m" % actual)
        if actual + 1e-9 >= need:
            print("判定：满足")
        else:
            print("★ 判定：不满足 —— 净空不足 %.3f m" % (need - actual))
            bad.append("水库区净空 %.3f m < %.3f m" % (actual, need))
        print("依据               : JTG D60-2015 3.4.3-5")
    else:  # dike
        if args.design_flood_level is None or args.struct_elev is None:
            print("输入错误：dike 需 --design-flood-level --struct-elev", file=sys.stderr)
            return 2
        need = 0.25
        actual = args.struct_elev - args.design_flood_level
        print("设计洪水位         : %.2f m" % args.design_flood_level)
        print("构造物顶面高程     : %.2f m" % args.struct_elev)
        print("实际超高           : %.2f m   （要求 ≥ %.2f m）" % (actual, need))
        if actual + 1e-9 >= need:
            print("判定：满足")
        else:
            print("★ 判定：不满足 —— 超高不足 %.2f m" % (need - actual))
            bad.append("构造物超高 %.2f m < 0.25 m" % actual)
        print("依据               : JTG D60-2015 3.2.8-2")

    print("-" * 60)
    if bad:
        print("★ 结论：不满足 —— " + "；".join(bad))
        rc = 1
    else:
        print("结论：满足")
        rc = 0
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
