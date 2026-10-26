#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""护岸 / 防洪墙稳定与护面复核器。

【两种模式】

  mode=stability（稳定安全系数校核）—— 机械比对报告值 vs 规范允许值：
    --type levee-slope        土堤边坡抗滑        GB 50286 表3.2.3（--method swedish|bishop）
    --type floodwall-slide    防洪墙沿基底抗滑     GB 50286 表3.2.5（--foundation rock|soil）
    --type floodwall-overturn 岩基防洪墙抗倾覆     GB 50286 表3.2.7
    --type bearing            地基承载力          GB 50286 表3.2.6（--soil 松软|中等坚实|坚实）
    --type protection-slope   坡式防护工程          GB 50707 表8.2.5（整体稳定 / 边坡内部稳定）
    --type protection-wall    墙式防护工程          GB 50707 表8.2.5（抗滑稳定 / 抗倾覆稳定）

  mode=armor（护面块体，Hudson）：W = γs·H³ / [K_D·(γs/γw − 1)³·cotα]

【用法】
    python calc_revetment.py --type levee-slope --level 2 --method bishop --case normal --report-k 1.28
    python calc_revetment.py --type floodwall-slide --level 3 --foundation soil --case abnormal1 --report-k 1.12
    python calc_revetment.py --type protection-slope --part internal --report-k 1.05
    python calc_revetment.py --mode armor --wave-h 1.2 --slope-m 3.0 --kd 4.0 --report-d 0.45

退出码：0 = 满足 / 无报告值；1 = 报告值不足。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— GB 50286 表3.2.3 土堤边坡抗滑稳定安全系数 ——
T323 = {
    "swedish": {"normal": {1: 1.30, 2: 1.25, 3: 1.20, 4: 1.15, 5: 1.10},
                "abnormal1": {1: 1.20, 2: 1.15, 3: 1.10, 4: 1.05, 5: 1.05},
                "abnormal2": {1: 1.10, 2: 1.05, 3: 1.05, 4: 1.00, 5: 1.00}},
    "bishop": {"normal": {1: 1.50, 2: 1.35, 3: 1.30, 4: 1.25, 5: 1.20},
               "abnormal1": {1: 1.30, 2: 1.25, 3: 1.20, 4: 1.15, 5: 1.10},
               "abnormal2": {1: 1.20, 2: 1.15, 3: 1.15, 4: 1.10, 5: 1.05}},
}
# —— GB 50286 表3.2.5 防洪墙沿基底面抗滑稳定安全系数 ——
T325 = {
    "rock": {"normal": {1: 1.15, 2: 1.10, 3: 1.08, 4: 1.05, 5: 1.05},
             "abnormal1": {1: 1.05, 2: 1.05, 3: 1.03, 4: 1.00, 5: 1.00},
             "abnormal2": {1: 1.03, 2: 1.03, 3: 1.00, 4: 1.00, 5: 1.00}},
    "soil": {"normal": {1: 1.35, 2: 1.30, 3: 1.25, 4: 1.20, 5: 1.20},
             "abnormal1": {1: 1.20, 2: 1.15, 3: 1.10, 4: 1.05, 5: 1.05},
             "abnormal2": {1: 1.10, 2: 1.05, 3: 1.05, 4: 1.00, 5: 1.00}},
}
# —— GB 50286 表3.2.6 地基承载力安全系数 ——
T326 = {"松软": {"basic": 1.50, "special": 2.00},
        "中等坚实": {"basic": 2.00, "special": 2.50},
        "坚实": {"basic": 2.50, "special": 3.00}}
# —— GB 50286 表3.2.7 岩基上防洪墙抗倾覆稳定安全系数 ——
T327 = {"normal": {1: 1.60, 2: 1.55, 3: 1.50, 4: 1.45, 5: 1.40},
        "abnormal1": {1: 1.50, 2: 1.45, 3: 1.40, 4: 1.35, 5: 1.30},
        "abnormal2": {1: 1.40, 2: 1.35, 3: 1.30, 4: 1.25, 5: 1.20}}
# —— GB 50707 表8.2.5 防护工程稳定安全系数 ——
T825 = {"protection-slope": {"overall": 1.25, "internal": 1.20},
        "protection-wall": {"slide": 1.25, "overturn": 1.50}}

CASE_CN = {"normal": "正常运用", "abnormal1": "非常运用 I（施工期）", "abnormal2": "非常运用 II（地震）"}


def main():
    ap = argparse.ArgumentParser(description="护岸/防洪墙稳定与护面复核")
    ap.add_argument("--mode", choices=["stability", "armor"], default="stability")
    ap.add_argument("--type", choices=["levee-slope", "floodwall-slide", "floodwall-overturn",
                                       "bearing", "protection-slope", "protection-wall"])
    ap.add_argument("--level", type=int, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--method", choices=["swedish", "bishop"], default="swedish")
    ap.add_argument("--foundation", choices=["rock", "soil"], default="soil")
    ap.add_argument("--case", choices=["normal", "abnormal1", "abnormal2"], default="normal")
    ap.add_argument("--soil", choices=["松软", "中等坚实", "坚实"])
    ap.add_argument("--comb", choices=["basic", "special"], default="basic")
    ap.add_argument("--part", choices=["overall", "internal", "slide", "overturn"])
    ap.add_argument("--report-k", type=float, default=None, help="报告给出的安全系数")
    # armor
    ap.add_argument("--wave-h", type=float, help="[armor] 波高 H（m）")
    ap.add_argument("--slope-m", type=float, help="[armor] 坡率 m=cotα")
    ap.add_argument("--kd", type=float, default=4.0, help="[armor] 稳定系数 K_D（表27，默认块石抛填二层4.0）")
    ap.add_argument("--gammas", type=float, default=26.5, help="[armor] 块体容重 kN/m³（默认26.5）")
    ap.add_argument("--gammaw", type=float, default=10.25, help="[armor] 水容重 kN/m³（默认10.25）")
    ap.add_argument("--report-d", type=float, default=None, help="[armor] 报告给出的块石粒径（m）")
    args = ap.parse_args()

    if args.mode == "armor":
        if args.wave_h is None or args.slope_m is None:
            ap.error("armor 模式需 --wave-h 与 --slope-m")
        W = args.gammas * args.wave_h ** 3 / (
            args.kd * (args.gammas / args.gammaw - 1) ** 3 * args.slope_m)
        D = (W / args.gammas) ** (1.0 / 3.0)
        print("=" * 62)
        print("护面块体复核（Hudson，GB 50286 附录 D / 表 27）")
        print("=" * 62)
        print("波高 H=%.3f m  坡率 m=%.2f  K_D=%.1f  γs=%.2f γw=%.2f" % (
            args.wave_h, args.slope_m, args.kd, args.gammas, args.gammaw))
        print("-" * 62)
        print("=> 块体重量 W : %.3f kN  (约 %.1f kg)" % (W, W / 9.81 * 1000))
        print("=> 等效粒径 D : %.3f m  (= (W/γs)^(1/3))" % D)
        fail = False
        if args.report_d is not None:
            ok = args.report_d + 1e-9 >= D
            print("-" * 62)
            print("报告粒径 D0=%.3f m → %s（应 ≥ %.3f m）" % (
                args.report_d, "满足" if ok else "偏小，稳定性不足", D))
            fail = not ok
        print("-" * 62)
        print("结论: %s" % ("★ 报告护面块石偏小" if fail else ("✔ 满足" if args.report_d else "已算出所需块体重量/粒径")))
        return 1 if fail else 0

    # —— stability 模式 ——
    if args.type is None:
        ap.error("stability 模式需 --type")
    print("=" * 62)
    print("稳定安全系数校核")
    print("=" * 62)
    allowed = None
    desc = ""
    if args.type == "levee-slope":
        if args.level is None:
            ap.error("levee-slope 需 --level")
        allowed = T323[args.method][args.case][args.level]
        desc = "GB 50286 表3.2.3 土堤边坡抗滑（%s，%s，%d级）" % (
            "瑞典圆弧法" if args.method == "swedish" else "简化毕肖普法", CASE_CN[args.case], args.level)
    elif args.type == "floodwall-slide":
        if args.level is None:
            ap.error("floodwall-slide 需 --level")
        allowed = T325[args.foundation][args.case][args.level]
        desc = "GB 50286 表3.2.5 防洪墙基底抗滑（%s，%s，%d级）" % (
            "岩基" if args.foundation == "rock" else "土基", CASE_CN[args.case], args.level)
    elif args.type == "floodwall-overturn":
        if args.level is None:
            ap.error("floodwall-overturn 需 --level")
        allowed = T327[args.case][args.level]
        desc = "GB 50286 表3.2.7 岩基防洪墙抗倾覆（%s，%d级）" % (CASE_CN[args.case], args.level)
    elif args.type == "bearing":
        if args.soil is None:
            ap.error("bearing 需 --soil")
        allowed = T326[args.soil][args.comb]
        desc = "GB 50286 表3.2.6 地基承载力（%s，%s组合）" % (
            args.soil, "基本" if args.comb == "basic" else "特殊")
    elif args.type in ("protection-slope", "protection-wall"):
        part = args.part
        if part is None:
            ap.error("protection 需 --part（坡式: overall|internal；墙式: slide|overturn）")
        allowed = T825[args.type][part]
        desc = "GB 50707 表8.2.5 防护工程稳定（%s %s）" % (
            "坡式" if args.type == "protection-slope" else "墙式", part)
    print("判定依据: %s" % desc)
    print("规范允许值: K ≥ %.2f" % allowed)
    fail = False
    if args.report_k is not None:
        ok = args.report_k + 1e-9 >= allowed
        print("-" * 62)
        print("报告安全系数: %.3f → %s" % (args.report_k, "满足" if ok else "★ 不满足（< 允许值）"))
        fail = not ok
    print("-" * 62)
    if args.type == "levee-slope" and args.case == "abnormal2":
        print("提示: 非常运用 II = 多年平均水位遭遇地震（GB 50286 9.2.2）")
    print("结论: %s" % ("★ 报告安全系数不足" if fail else ("✔ 满足" if args.report_k else "已给出允许值")))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
