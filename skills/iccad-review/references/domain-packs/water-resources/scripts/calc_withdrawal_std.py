#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""等级·退水·纳污复算器 —— 核"论证工作等级 / 退水量与入河量 / 纳污能力 / 总量控制"
（水资源论证报告审查用）。

【它解决什么】
    ① 工作等级定错 → 全篇论证深度错（一级要做数值模型，三级可用类比法）。
       表1 的分级指标**单位并不统一**：地表水农业取水量用 m³/s，其余用 万m³/d，
       这是最容易被套错的一处。
    ② 退水量与污染物入河量算错 → 影响论证结论失真。
    ③ 入河量超水域纳污能力 / 取水量超用水总量控制指标 → 属实质性不满足。

【依据】
    GB/T 35580-2017 5.2.1 / 表1   工作等级由分类等级中的最高级别确定
    GB/T 35580-2017 5.2.2        等级调整（小型灌区可降一级；高耗水重污染应升一级）
    GB/T 35580-2017 3.10         退水量定义
    GB/T 35580-2017 11.2.3       退水污染负荷须符合水域纳污能力和限制排污总量控制要求
    GB/T 35580-2017 11.2.5       未提出限制排污总量意见的水域按 GB/T 25173 核算纳污能力
    GB/T 35580-2017 9.1.1        满足用水总量控制要求
    GB/T 25173                   水域纳污能力计算规程（本工具用零维充分混合简化式）

【用法】
    # 工作等级（地表水，工业 3.2 万m³/d，开发程度 35%）
    python calc_withdrawal_std.py --mode level --source 地表 --kind 工业 --value 3.2 --develop 35
    # 工作等级（地下水，农业 12 万m³/d，水文地质条件 中等）
    python calc_withdrawal_std.py --mode level --source 地下 --kind 农业 --value 12 --geo 中等

    # 退水量与污染物入河量
    python calc_withdrawal_std.py --mode retreat --intake 1200 --ratio 0.38 --conc 25 --days 365
    # 纳污能力（河流零维）
    python calc_withdrawal_std.py --mode capacity --cs 20 --c0 15 --flow 8.5 --load 380
    # 用水总量控制
    python calc_withdrawal_std.py --mode alloc --withdrawal 1200 --control-total 5200 --current-use 4300

【退出码】统一语义（家族约定，勿改）
    0 = 满足
    1 = 不满足（超纳污能力 / 超总量控制指标 / 等级定低 / 与报告不符）
    2 = 输入错
    3 = 仅参考值

【判据方向纪律】
    纳污能力、总量控制指标均为**上限型**（入河量/取水量 ≤ 上限）；
    工作等级不是"越大越好"而是**深度要求**，等级定低即为错情（取最严）。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表1 取水水源分级指标 ——
#   每项：(一级阈值, 二级阈值)；判定：v ≥ 一级 → 一级；v ≥ 二级 → 二级；否则三级
#   注意单位差异：地表水农业为 m³/s，其余为 万m³/d
LEVEL_TABLE = {
    "地表": {
        "农业": {"unit": "m³/s", "l1": 20.0, "l2": 3.0},
        "工业": {"unit": "万m³/d", "l1": 2.5, "l2": 1.0},
        "生活": {"unit": "万m³/d", "l1": 15.0, "l2": 5.0},
        "开发": {"unit": "%", "l1": 30.0, "l2": 10.0},
    },
    "地下": {
        "农业": {"unit": "万m³/d", "l1": 10.0, "l2": 2.0},
        "工业": {"unit": "万m³/d", "l1": 1.0, "l2": 0.3},
        "生活": {"unit": "万m³/d", "l1": 5.0, "l2": 1.0},
        "开发": {"unit": "%", "l1": 70.0, "l2": 50.0},
    },
}

GRADE_NUM = {"一级": 1, "二级": 2, "三级": 3}
GEO_GRADE = {"复杂": "一级", "中等": "二级", "简单": "三级"}

# 5.2.2 b) 应提高一级的行业
HIGH_LOAD = ("火电", "核电", "石化", "化工", "纺织", "造纸", "钢铁", "食品")


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _grade(v, l1, l2):
    if v >= l1:
        return "一级"
    if v >= l2:
        return "二级"
    return "三级"


def main():
    ap = argparse.ArgumentParser(description="水资源论证 · 等级与退水纳污复算")
    ap.add_argument("--mode", required=True, choices=["level", "retreat", "capacity", "alloc"])
    # level
    ap.add_argument("--source", default="地表", choices=["地表", "地下"])
    ap.add_argument("--kind", default="工业", choices=["农业", "工业", "生活"])
    ap.add_argument("--value", type=float, default=None, help="取水量（单位见 kind/source）")
    ap.add_argument("--develop", type=float, default=None, help="开发利用程度（%%）")
    ap.add_argument("--geo", default=None, choices=["复杂", "中等", "简单"], help="供水水文地质条件")
    ap.add_argument("--industry", default=None, help="行业名（用于 5.2.2 提级判断）")
    ap.add_argument("--small-irrigation", action="store_true", help="水资源丰沛地区小型灌区（5.2.2a 可降一级）")
    # retreat
    ap.add_argument("--intake", type=float, default=None, help="取水量（万m³/a）")
    ap.add_argument("--ratio", type=float, default=None, help="退水系数（退水/取水）")
    ap.add_argument("--conc", type=float, default=None, help="污染物浓度（mg/L）")
    ap.add_argument("--days", type=float, default=365.0, help="运行天数（默认 365）")
    # capacity
    ap.add_argument("--cs", type=float, default=None, help="水质目标浓度 Cs（mg/L）")
    ap.add_argument("--c0", type=float, default=None, help="现状/来水浓度 C0（mg/L）")
    ap.add_argument("--flow", type=float, default=None, help="设计流量 Q（m³/s）")
    ap.add_argument("--load", type=float, default=None, help="污染物入河量（kg/d）")
    # alloc
    ap.add_argument("--withdrawal", type=float, default=None, help="拟取水量（万m³/a）")
    ap.add_argument("--control-total", type=float, default=None, help="区域用水总量控制指标（万m³/a）")
    ap.add_argument("--current-use", type=float, default=None, help="现状已用水量（万m³/a）")
    # 通用
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的对应结论值")
    ap.add_argument("--tol", type=float, default=0.05, help="相对容差（默认 0.05）")
    args = ap.parse_args()

    bad = []
    rc = 0

    if args.mode == "level":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 5.2.1 + 表1（工作等级取分类等级中的最高级别）")
        print("-" * 66)
        if args.value is None and args.develop is None and args.geo is None:
            print("★ 输入错：level 模式至少给 --value / --develop / --geo 之一")
            return 2
        grades = []

        if args.value is not None:
            t = LEVEL_TABLE[args.source][args.kind]
            g = _grade(args.value, t["l1"], t["l2"])
            grades.append(("取水量（%s）" % args.kind, g))
            print("  %-22s : %s %-7s → %s" % (
                "取水量（%s）" % args.kind, _f(args.value), t["unit"], g))
            print("      阈值：≥%s 一级；%s~%s 二级；<%s 三级"
                  % (_f(t["l1"]), _f(t["l2"]), _f(t["l1"]), _f(t["l2"])))
            if args.source == "地表" and args.kind == "农业":
                print("      ⚠ 地表水农业取水量的单位是 m³/s（不是 万m³/d）—— 本域最易套错的一处")

        if args.develop is not None:
            t = LEVEL_TABLE[args.source]["开发"]
            g = _grade(args.develop, t["l1"], t["l2"])
            grades.append(("开发利用程度", g))
            print("  %-22s : %s %-7s → %s" % ("开发利用程度", _f(args.develop, 1), "%", g))

        if args.geo is not None and args.source == "地下":
            g = GEO_GRADE[args.geo]
            grades.append(("供水水文地质条件", g))
            print("  %-22s : %-9s → %s" % ("供水水文地质条件", args.geo, g))

        if not grades:
            print("  ⚠ 未给出可判级指标（水文地质条件仅对地下水适用）")
            return 3

        worst = min(grades, key=lambda x: GRADE_NUM[x[1]])
        print("-" * 66)
        print("  分类等级明细         : %s" % "；".join("%s=%s" % (k, v) for k, v in grades))
        print("  → 综合工作等级       : %s（取最高级别 = 最严）" % worst[1])
        level_num = GRADE_NUM[worst[1]]

        # 5.2.2 调整
        if args.industry and any(k in args.industry for k in HIGH_LOAD):
            new = max(1, level_num - 1)
            print("  5.2.2b 高耗水/重污染行业（%s）应提高一级 → **%s**"
                  % (args.industry, {1: "一级", 2: "二级", 3: "三级"}[new]))
            level_num = new
        if args.small_irrigation and args.kind == "农业":
            new = min(3, level_num + 1)
            print("  5.2.2a 水资源丰沛地区小型灌区可降低一级 → **%s**（最低三级）"
                  % {1: "一级", 2: "二级", 3: "三级"}[new])
            level_num = new

        final = {1: "一级", 2: "二级", 3: "三级"}[level_num]
        print("  → 最终工作等级       : %s" % final)
        if args.report is not None:
            rmap = {1: 1, 2: 2, 3: 3}
            r = int(args.report) if args.report in (1, 2, 3) else rmap.get(int(args.report), None)
            if r is None:
                print("  ⚠ --report 仅接受 1/2/3（对应当前等级）")
            elif r > level_num:
                bad.append("报告定为 %s，按表1 应为 %s —— **等级定低，论证深度不足**"
                           % ({1: "一级", 2: "二级", 3: "三级"}[r], final))
            elif r < level_num:
                print("  报告定为 %s，严于复算的 %s（偏严不构成错情，但要核其工作量是否匹配）"
                      % ({1: "一级", 2: "二级", 3: "三级"}[r], final))
            else:
                print("  报告等级与复算一致")

    elif args.mode == "retreat":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 3.10 / 11.2.2 / 11.2.3")
        print("口径 : W退 = W取 × 退水系数；污染物入河量(t) = V(m³) × C(mg/L) × 1e-6")
        print("-" * 66)
        if args.intake is None:
            print("★ 输入错：retreat 模式须给 --intake（万m³/a）")
            return 2
        if args.ratio is None and args.report is None:
            print("★ 输入错：须给 --ratio（退水系数）或用 --report 直接给退水量")
            return 2
        ret = args.intake * args.ratio if args.ratio is not None else args.report
        print("  取水量 W取           : %s 万m³/a" % _f(args.intake, 1))
        if args.ratio is not None:
            print("  退水系数             : %.3f" % args.ratio)
            if args.ratio < 0 or args.ratio > 1:
                bad.append("退水系数 %.3f 超出 0~1" % args.ratio)
        print("  → 退水量 W退         : %s 万m³/a" % _f(ret, 1))
        if args.report is not None and args.ratio is not None:
            dev = abs(ret - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= args.tol
            print("  报告退水量           : %s ｜偏差 %.2f%%  %s" % (
                _f(args.report, 1), dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("退水量复算 %s vs 报告 %s" % (_f(ret, 1), _f(args.report, 1)))
        if args.conc is not None:
            vol = ret * 1e4  # 万m³ → m³
            load_t = vol * args.conc * 1e-6
            load_kgd = load_t * 1000.0 / args.days if args.days else None
            print("  特征污染物浓度       : %s mg/L" % _f(args.conc, 2))
            print("  → 污染物年入河量     : %s t/a" % _f(load_t, 2))
            print("  → 折日均入河量       : %s kg/d" % _f(load_kgd, 2))
            print("     （可直接喂给 --mode capacity --load）")

    elif args.mode == "capacity":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 11.2.5 + GB/T 25173（水域纳污能力计算规程）")
        print("式   : M = 86.4 × (Cs − C0) × Q   [kg/d；Q 取 m³/s，C 取 mg/L]")
        print("适用 : **零维（充分混合）简化式** —— 仅适用于污染物入河后能迅速混合的小型河段；")
        print("       一级论证或大江大河应改用报告自身的二维/三维模型结果，本式只作量级校核。")
        print("-" * 66)
        if args.cs is None or args.c0 is None or args.flow is None:
            print("★ 输入错：capacity 模式须给 --cs / --c0 / --flow")
            return 2
        cap = 86.4 * (args.cs - args.c0) * args.flow
        print("  水质目标 Cs          : %s mg/L" % _f(args.cs, 2))
        print("  现状浓度 C0          : %s mg/L" % _f(args.c0, 2))
        print("  设计流量 Q           : %s m³/s" % _f(args.flow, 3))
        print("  → 纳污能力 M         : %s kg/d" % _f(cap, 2))
        if cap <= 0:
            print("  ★ Cs ≤ C0 —— 该水域已无剩余纳污能力（容量 ≤ 0），不得新增排污")
            bad.append("纳污能力 %s ≤ 0（Cs=%s ≤ C0=%s），水域无剩余容量"
                       % (_f(cap, 2), _f(args.cs, 2), _f(args.c0, 2)))
        if args.load is not None:
            ok = args.load <= cap + 1e-9
            print("  项目入河量           : %s kg/d  %s 纳污能力  %s" % (
                _f(args.load, 2), "≤" if ok else "★>", _f(cap, 2)))
            if not ok:
                bad.append("入河量 %s kg/d > 纳污能力 %s kg/d（超出 %s）"
                           % (_f(args.load, 2), _f(cap, 2), _f(args.load - cap, 2)))
            elif cap > 0:
                print("  占用水域容量比例     : %.1f%%" % (args.load / cap * 100.0))
                if args.load / cap > 0.8:
                    print("  ⚠ 占用水域容量 > 80%%，须核是否与已审批排污口叠加（11.1.2/11.2.3）")

    elif args.mode == "alloc":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 9.1.1（用水总量控制）+ 7.4.1（开发利用潜力）")
        print("口径 : 可用余量 = 总量控制指标 − 现状已用水量；取水量须 ≤ 可用余量")
        print("-" * 66)
        if args.withdrawal is None or args.control_total is None:
            print("★ 输入错：alloc 模式须给 --withdrawal 与 --control-total")
            return 2
        cur = args.current_use or 0.0
        room = args.control_total - cur
        print("  区域总量控制指标     : %s 万m³/a" % _f(args.control_total, 1))
        print("  现状已用水量         : %s 万m³/a" % _f(cur, 1))
        print("  → 可用余量           : %s 万m³/a" % _f(room, 1))
        print("  拟取水量             : %s 万m³/a" % _f(args.withdrawal, 1))
        if room <= 0:
            print("  ★ 区域已无用水总量余量，新增取水不符合总量控制要求")
            bad.append("可用余量 %s ≤ 0，区域用水总量已无空间" % _f(room, 1))
        else:
            ok = args.withdrawal <= room + 1e-9
            print("  占用余量比例         : %.1f%%  %s" % (
                args.withdrawal / room * 100.0, "满足" if ok else "**超出**"))
            if not ok:
                bad.append("拟取水 %s > 可用余量 %s（超出 %s）"
                           % (_f(args.withdrawal, 1), _f(room, 1), _f(args.withdrawal - room, 1)))
            print("  取水后区域开发程度   : 余量剩 %s 万m³/a" % _f(room - args.withdrawal, 1))

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
