#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重力式码头稳定验算项完备性核对（水运工程报告审查用）。

【为什么这个脚本不算安全系数】
    水利规范用**单一安全系数 K**（如抗滑 K≥1.1），水运用**极限状态分项系数**：
    JTS 167—2018 7.3.2 抗滑、7.3.4 抗倾的公式是
        γ0(γE·EH + γw·Pw + γE·EqH·ψ + γPR·PRH) ≤ ……
    左边是"作用效应设计值"，右边是"抗力设计值"，**不存在可以直接与 1.1/1.3 比对的 K**。
    因此本脚本不做 K 判限值（做了就是编判据），只核"规范要求的验算项，报告做了没有"。

【依据】
    JTS 167—2018  7.1.12  承载能力极限状态·持久组合应验算 7 项：
                            ① 墙底面/墙身水平缝/齿缝计算面前趾抗倾
                            ② 沿墙底面和墙身各水平缝抗滑
                            ③ 沿基床底面抗滑
                            ④ 基床和地基承载力
                            ⑤ 墙底面合力作用位置
                            ⑥ 整体稳定
                            ⑦ 卸荷板、沉箱、扶壁、空心块体、圆筒等构件承载力
    JTS 167—2018  3.2.6   作用组合：持久组合 / 短暂组合 / 地震组合（必要时应偶然组合）
    JTS 167—2018  7.1.10  沿计算面摩擦系数设计值（表7.1.10）
    JTS 167—2018  7.2.5   抛石基床厚度：基床顶面应力大于地基承载力时按承载力计算且不小于 1m；
                           不大于时不小于 0.5m
    JTS 167—2018  7.2.16  抛石基床应预留沉降量；基床顶面向墙后倾斜坡度 0～1.5%

【用法】
    python calc_wharf_stability.py --mode checklist --done 1,2,3,4,5,6,7
    python calc_wharf_stability.py --mode checklist --done 1,2,4,6 --bed 0.8 --stress-ratio 0.85
    python calc_wharf_stability.py --mode bed --stress 320 --capacity 260 --thickness 1.2

【退出码】0 齐全 / 1 有缺项（含基床厚度不满足）/ 2 输入错 / 3 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ITEMS = [
    (1, "前趾抗倾稳定", "墙底面、墙身各水平缝、齿缝计算面", "7.1.12(1)"),
    (2, "沿墙底面及墙身水平缝抗滑", "摩擦系数按表7.1.10", "7.1.12(2)"),
    (3, "沿基床底面抗滑", "置换/换填地基时尤须做", "7.1.12(3)"),
    (4, "基床和地基承载力", "含软弱下卧层验算", "7.1.12(4)"),
    (5, "墙底面合力作用位置", "控制偏心，避免基底脱空", "7.1.12(5)"),
    (6, "整体稳定性", "含岸坡/地基整体滑动", "7.1.12(6)"),
    (7, "构件承载力", "卸荷板/沉箱/扶壁/空心块体/圆筒", "7.1.12(7)"),
]
COMBOS = {
    "persistent": "持久组合",
    "transient": "短暂组合",
    "seismic": "地震组合",
    "accidental": "偶然组合（有特殊要求时）",
}


def _fmt(v, f="%.2f"):
    return f % v if v is not None else "-"


def main():
    ap = argparse.ArgumentParser(description="重力式码头验算项完备性核对（JTS 167—2018 7.1.12）")
    ap.add_argument("--mode", required=True, choices=["checklist", "bed"])
    ap.add_argument("--done", default="", help="[checklist] 报告已做的验算项编号，逗号分隔，如 1,2,4,6")
    ap.add_argument("--combo", default="persistent", choices=list(COMBOS), help="[checklist] 作用组合")
    ap.add_argument("--bed", type=float, default=None, help="[checklist] 抛石基床厚度，m")
    ap.add_argument("--stress", type=float, default=None, help="[bed] 基床顶面应力，kPa")
    ap.add_argument("--capacity", type=float, default=None, help="[bed] 地基承载力特征值，kPa")
    ap.add_argument("--thickness", type=float, default=None, help="[bed] 基床厚度，m")
    args = ap.parse_args()

    if args.mode == "checklist":
        done = set()
        for tok in (args.done or "").replace("，", ",").split(","):
            tok = tok.strip()
            if tok.isdigit():
                done.add(int(tok))
        miss = [it for it in ITEMS if it[0] not in done]

        print("=" * 70)
        print("依据            : JTS 167—2018 7.1.12（持久组合）+ 3.2.6（作用组合）")
        print("作用组合        : %s" % COMBOS[args.combo])
        print("-" * 70)
        print("%-4s %-26s %-16s %s" % ("#", "验算项", "条款", "报告是否给出"))
        for no, name, note, src in ITEMS:
            print("%-4d %-26s %-16s %s" % (no, name, src, "✔ 已做" if no in done else "✗ 未见"))
        print("-" * 70)
        if args.combo == "persistent" and "transient" not in (args.done or ""):
            print("  ▲ 提示：3.2.6 还要求短暂组合（施工期）验算，若报告有施工期工况须单独核")

        bad = []
        if miss:
            print("缺项 %d / %d：%s" % (len(miss), len(ITEMS), "、".join("%d %s" % (n, s) for n, s, _, _ in miss)))
            bad.append("缺 %d 项验算" % len(miss))
        else:
            print("7 项验算齐备")

        # 基床厚度（7.2.5）：应力大于承载力时按承载力计算且 ≥1m；否则 ≥0.5m
        if args.bed is not None:
            print("-" * 70)
            print("抛石基床厚度    : %.2f m" % args.bed)
            if args.bed < 0.5 - 1e-9:
                print("  ★ 基床厚度 %.2f m < 0.5m（7.2.5 最小值）" % args.bed)
                bad.append("基床厚度 %.2f < 0.5m" % args.bed)
            elif args.bed < 1.0 - 1e-9:
                print("  ▲ 提示：厚度 %.2f m 在 0.5~1.0m 之间，仅当基床顶面应力不大于地基承载力时适用"
                      "（7.2.5(2)）" % args.bed)
            else:
                print("  ✓ 厚度满足 7.2.5")

        print("=" * 70)
        if bad:
            print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
            return 1
        print("判定：验算项齐全")
        return 0

    # bed 模式：只核基床厚度与应力/承载力关系
    if args.thickness is None:
        print("★ 输入错：--thickness 必填", file=sys.stderr)
        return 2
    print("=" * 70)
    print("依据            : JTS 167—2018 7.2.5")
    need = 1.0
    if args.stress is not None and args.capacity is not None:
        if args.stress > args.capacity + 1e-9:
            need = 1.0
            print("基床顶面应力 %.0f kPa > 地基承载力 %.0f kPa" % (args.stress, args.capacity))
            print("→ 应按地基承载力计算确定，且厚度不小于 1.0m")
        else:
            need = 0.5
            print("基床顶面应力 %.0f kPa ≤ 地基承载力 %.0f kPa" % (args.stress, args.capacity))
            print("→ 厚度不小于 0.5m")
    print("厚度要求        : ≥ %.2f m；报告 %.2f m" % (need, args.thickness))
    print("=" * 70)
    if args.thickness < need - 1e-9:
        print("★ 判定：不满足 —— 基床厚度 %.2f m < %.2f m" % (args.thickness, need))
        return 1
    print("判定：满足")
    return 0


if __name__ == "__main__":
    sys.exit(main())
