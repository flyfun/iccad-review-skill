#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泵站等别·建筑物级别·防洪标准复核（泵站工程报告审查用）。

【它解决什么】
    泵站级别与防洪标准是"**定错则全篇连锁错**"的根节点。报告常犯：
    ① 供水泵站误用表 4.5.3（应用表 4.7.1）；② 只看设计流量不看装机功率；
    ③ 穿堤泵站防洪标准**等于**堤防标准（漏"留安全裕度"）；④ 只按级别取设计重现期、漏校核。
    本工具按 SL 252 独立核定，并与报告值比对。

【依据】
    SL 252-2017：
      4.5.3 ★ 治涝、排水工程泵站永久性水工建筑物级别（设计流量 + 装机功率，表 4.5.3）
      4.6.2 ★ 灌溉工程泵站永久性水工建筑物级别（同表 4.5.3）
      4.7.1 ★ 供水工程泵站永久性水工建筑物级别（表 4.7.1）
      5.5.3 ★ 泵站永久性水工建筑物洪水标准（表 5.5.3）
      5.1.4   堤防、渠道上的闸涵泵站洪水标准不应低于堤防、渠道防洪标准并留安全裕度
    GB 50201-2014 11.8.3 ★ 堤防工程上的闸、涵、泵站设计防洪标准不应低于堤防并留安全裕度

【用法】
    # 1) 定建筑物级别（灌溉/排水/治涝）
    python calc_pump_std.py --mode level --kind 灌溉 --q 12 --power 2.5
    # 2) 供水泵站（走表 4.7.1）
    python calc_pump_std.py --mode level --kind 供水 --q 12 --power 2.5
    # 3) 级别 → 洪水标准
    python calc_pump_std.py --mode flood-standard --level 3
    # 4) 项目防洪标准 vs 河道/堤防（穿堤时须严格大于）
    python calc_pump_std.py --mode check --project-std 50 --river-std 50 --through-dike

【退出码】统一语义（家族约定，勿改）
    0 = 满足 · 1 = 不满足（含违反强条）· 2 = 输入错 · 3 = 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— SL 252 表 4.5.3 治涝/排水/灌溉泵站：(设计流量 m³/s 下限, 装机功率 MW 下限) → (主, 次) ——
T453 = [(200.0, 30.0, 1), (50.0, 10.0, 2), (10.0, 1.0, 3), (2.0, 0.1, 4)]
# —— SL 252 表 4.7.1 供水泵站 ——
T471 = [(50.0, 30.0, 1), (10.0, 10.0, 2), (3.0, 1.0, 3), (1.0, 0.1, 4)]
# 主要建筑物级别 → 次要建筑物级别
SECONDARY = {1: 3, 2: 3, 3: 4, 4: 5, 5: 5}
# —— SL 252 表 5.5.3 泵站洪水标准：级别 → (设计, 校核) 重现期(年) ——
FLOOD_STD = {1: (100, 300), 2: (50, 200), 3: (30, 100), 4: (20, 50), 5: (10, 20)}


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _grade(value, table):
    """返回按单一指标得到的级别（1~5）。"""
    for lo, _p, lv in table:
        if value >= lo - 1e-9:
            return lv
    return 5


def mode_level(a, bad, warn):
    if a.q is None or a.power is None:
        print("  ★ level 需要 --q（设计流量 m³/s）与 --power（装机功率 MW，含备用机组）", file=sys.stderr)
        return 2
    kind = (a.kind or "灌溉").strip()
    table = T471 if kind in ("供水", "城镇供水", "工业供水") else T453
    tname = "表 4.7.1（供水）" if table is T471 else "表 4.5.3（治涝/排水/灌溉）"
    if kind in ("供水", "城镇供水", "工业供水"):
        ref = "SL 252 4.7.1 ★"
    elif kind == "灌溉":
        ref = "SL 252 4.6.2 ★"
    else:
        ref = "SL 252 4.5.3 ★"
    lv_q = _grade(a.q, table)
    lv_p = _grade(a.power, table)
    lv = min(lv_q, lv_p)            # 取高者 = 级别数字小者
    gov = "设计流量" if lv_q <= lv_p else "装机功率"
    print("依据               : %s %s" % (ref, tname))
    print("  泵站类型           : %s" % kind)
    print("  设计流量 / 装机功率 : %s m³/s / %s MW" % (_f(a.q), _f(a.power)))
    print("-" * 62)
    print("  按设计流量定级     : %d 级" % lv_q)
    print("  按装机功率定级     : %d 级" % lv_p)
    print("  → 取高者（级别小者）: **%d 级**（受控于%s）" % (lv, gov))
    print("  → 主要建筑物 %d 级 / 次要建筑物 %d 级" % (lv, SECONDARY[lv]))
    if a.report is not None:
        try:
            rl = int(a.report)
            ok = (rl == lv)
            print("  %-28s : 报告 %d 级  %s" % ("与报告级别比对", rl, "一致" if ok else "★ 不一致"))
            if not ok:
                bad.append("报告建筑物级别 %d 级 ≠ 复算 %d 级" % (rl, lv))
        except Exception:
            print("  ▲ --report 非整数级别，跳过比对")


def mode_flood_standard(a, bad, warn):
    if a.level is None:
        print("  ★ flood-standard 需要 --level（主要建筑物级别 1~5）", file=sys.stderr)
        return 2
    try:
        lv = int(a.level)
    except Exception:
        print("  ★ --level 应为 1~5 整数", file=sys.stderr)
        return 2
    if lv not in FLOOD_STD:
        print("  ★ --level 超范围（应 1~5）", file=sys.stderr)
        return 2
    des, chk = FLOOD_STD[lv]
    print("依据               : SL 252 5.5.3 ★ 表 5.5.3")
    print("  主要建筑物级别     : %d 级" % lv)
    print("  → 设计洪水标准     : %d 年一遇" % des)
    print("  → 校核洪水标准     : %d 年一遇" % chk)
    print("  ▲ 穿堤/堤上布置时还须满足「不应低于堤防防洪标准并留安全裕度」（11.8.3 ★），见 --mode check。")


def mode_check(a, bad, warn):
    if a.project_std is None or a.river_std is None:
        print("  ★ check 需要 --project-std（项目防洪标准 重现期年）与 --river-std（河道/堤防防洪标准 重现期年）",
              file=sys.stderr)
        return 2
    print("依据               : GB 50201 11.8.3 ★ / SL 252 5.1.4")
    print("  项目防洪标准       : %s 年一遇" % _f(a.project_std, 0))
    print("  河道/堤防防洪标准  : %s 年一遇" % _f(a.river_std, 0))
    print("  布置方式           : %s" % ("穿堤/位于堤防工程上" if a.through_dike else "非穿堤（按一般不低于校验）"))
    print("-" * 62)
    if a.through_dike:
        ok = a.project_std > a.river_std + 1e-9      # 严格大于（留安全裕度）
        print("  %-28s : %s  %s  严格大于   %s" % (
            "项目标准 vs 河道标准", _f(a.project_std, 0), ">" if ok else "★≤", _f(a.river_std, 0)))
        if not ok:
            bad.append("穿堤泵站防洪标准 %s 年 ≤ 堤防 %s 年，未留安全裕度（违反 11.8.3 ★）" % (
                _f(a.project_std, 0), _f(a.river_std, 0)))
            print("  ★ 触发强制性条文：GB 50201 11.8.3（不应低于 + 留安全裕度 ⇒ **等于也不满足**）")
    else:
        ok = a.project_std >= a.river_std - 1e-9
        print("  %-28s : %s  %s  不低于   %s" % (
            "项目标准 vs 河道标准", _f(a.project_std, 0), "≥" if ok else "★<", _f(a.river_std, 0)))
        if not ok:
            bad.append("项目防洪标准 %s 年 < 河道 %s 年" % (_f(a.project_std, 0), _f(a.river_std, 0)))
        elif abs(a.project_std - a.river_std) < 1e-9:
            warn.append("项目标准等于河道标准；若泵站穿堤/位于堤防工程上，须**严格大于**以留安全裕度（11.8.3 ★）")


def main():
    ap = argparse.ArgumentParser(description="泵站等别·建筑物级别·防洪标准复核")
    ap.add_argument("--mode", required=True, choices=["level", "flood-standard", "check"])
    ap.add_argument("--kind", default="灌溉", help="泵站类型：灌溉 / 排水 / 治涝 / 供水")
    ap.add_argument("--q", type=float, help="设计流量 (m³/s)")
    ap.add_argument("--power", type=float, help="装机功率 (MW)，含备用机组")
    ap.add_argument("--level", type=float, default=None, help="主要建筑物级别 1~5")
    ap.add_argument("--project-std", type=float, dest="project_std", help="项目防洪标准 重现期(年)")
    ap.add_argument("--river-std", type=float, dest="river_std", help="河道/堤防防洪标准 重现期(年)")
    ap.add_argument("--through-dike", action="store_true", dest="through_dike",
                    help="泵站穿堤或位于堤防工程上（触发 11.8.3 ★ 严格大于校验）")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的级别/标准，用于比对")
    args = ap.parse_args()

    bad, warn = [], []
    print("=" * 62)
    if args.mode == "level":
        rc = mode_level(args, bad, warn)
    elif args.mode == "flood-standard":
        rc = mode_flood_standard(args, bad, warn)
    else:
        rc = mode_check(args, bad, warn)
    if rc == 2:
        return 2

    print("=" * 62)
    for w in warn:
        print("▲ 提示：%s" % w)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足")
    return 0


if __name__ == "__main__":
    sys.exit(main())
