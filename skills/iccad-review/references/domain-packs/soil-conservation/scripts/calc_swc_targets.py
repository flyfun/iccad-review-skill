#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水土流失防治指标达标复核器 —— 依 GB/T 50434-2018《生产建设项目水土流失防治标准》。

【干什么】
    报告给出六项防治指标（水土流失治理度、土壤流失控制比、渣土防护率、表土保护率、
    林草植被恢复率、林草覆盖率），本脚本按 **水土保持区划 + 防治标准等级 + 时段**
    查出规范限值（表 4.0.2-1～表 4.0.2-8），逐项判"达标 / 不达标"，并提示可适用的
    调整情形（4.0.5～4.0.10）。

【限值来源】
    GB/T 50434-2018 表 4.0.2-1～表 4.0.2-8，实测自本机原始 docx（非记忆）。
    8 区 × 3 等级 × 2 时段（施工期 / 设计水平年）。
    注：施工期只对"渣土防护率""表土保护率"有要求；治理度/控制比/植被恢复率/覆盖率
    在设计水平年才有值，施工期标"不作要求"。

【用法】
    python calc_swc_targets.py --region 南方红壤区 --level 1 --period design \\
        --governed 96 --ratio 0.88 --dregs 96 --topsoil 90 --veg-restore 96 --veg-cover 24

    # 只想看某区某等级的限值表
    python calc_swc_targets.py --region 东北黑土区 --level 2 --show-table

    # 施工期：只核 渣土防护率 / 表土保护率
    python calc_swc_targets.py --region 西北黄土高原区 --level 3 --period construct --dregs 86 --topsoil 82

    # 调整情形（可选，会打印适用规则）
    --arid extreme|arid           # 4.0.6 极干旱/干旱
    --erosion light|moderate      # 4.0.7 轻度侵蚀(控制比≥1) / 中度以上(可降0.1~0.2)
    --terrain mid|high            # 4.0.8 中山区(-1~3%) / 极高·高山区(-3~5%) 渣土防护率
    --urban                       # 4.0.9 城市区 渣土防护率与林草覆盖率 +1~2%

【退出码】
    0 = 全部达标；1 = 有指标不达标；2 = 参数不足 / 非法。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REGIONS = ["东北黑土区", "北方风沙区", "北方土石山区", "西北黄土高原区",
           "南方红壤区", "西南紫色土区", "西南岩溶区", "青藏高原区"]

# 指标键：govern 治理度(%) / ratio 控制比 / dregs 渣土防护率(%) /
#         topsoil 表土保护率(%) / veg_restore 植被恢复率(%) / veg_cover 覆盖率(%)
IND_NAMES = {
    "govern": "水土流失治理度(%)", "ratio": "土壤流失控制比", "dregs": "渣土防护率(%)",
    "topsoil": "表土保护率(%)", "veg_restore": "林草植被恢复率(%)", "veg_cover": "林草覆盖率(%)",
}

# GB/T 50434-2018 表 4.0.2-1～8（None = 不作要求；风沙区表土保护率不作要求，标注 "B")
TARGETS = {
    "东北黑土区": {
        1: {"construct": {"dregs": 95, "topsoil": 98},
            "design": {"govern": 97, "ratio": 0.90, "dregs": 97, "topsoil": 98, "veg_restore": 97, "veg_cover": 25}},
        2: {"construct": {"dregs": 90, "topsoil": 95},
            "design": {"govern": 94, "ratio": 0.85, "dregs": 92, "topsoil": 95, "veg_restore": 95, "veg_cover": 22}},
        3: {"construct": {"dregs": 85, "topsoil": 92},
            "design": {"govern": 89, "ratio": 0.80, "dregs": 90, "topsoil": 92, "veg_restore": 90, "veg_cover": 19}},
    },
    "北方风沙区": {
        1: {"construct": {"dregs": 85},
            "design": {"govern": 85, "ratio": 0.80, "dregs": 87, "veg_restore": 93, "veg_cover": 20}},
        2: {"construct": {"dregs": 83},
            "design": {"govern": 82, "ratio": 0.75, "dregs": 85, "veg_restore": 88, "veg_cover": 16}},
        3: {"construct": {"dregs": 80},
            "design": {"govern": 77, "ratio": 0.70, "dregs": 83, "veg_restore": 83, "veg_cover": 12}},
    },
    "北方土石山区": {
        1: {"construct": {"dregs": 95, "topsoil": 95},
            "design": {"govern": 95, "ratio": 0.90, "dregs": 97, "topsoil": 95, "veg_restore": 97, "veg_cover": 25}},
        2: {"construct": {"dregs": 90, "topsoil": 92},
            "design": {"govern": 92, "ratio": 0.85, "dregs": 95, "topsoil": 92, "veg_restore": 95, "veg_cover": 22}},
        3: {"construct": {"dregs": 85, "topsoil": 90},
            "design": {"govern": 87, "ratio": 0.80, "dregs": 90, "topsoil": 90, "veg_restore": 90, "veg_cover": 19}},
    },
    "西北黄土高原区": {
        1: {"construct": {"dregs": 90, "topsoil": 90},
            "design": {"govern": 93, "ratio": 0.80, "dregs": 92, "topsoil": 90, "veg_restore": 95, "veg_cover": 22}},
        2: {"construct": {"dregs": 85, "topsoil": 85},
            "design": {"govern": 90, "ratio": 0.75, "dregs": 88, "topsoil": 85, "veg_restore": 90, "veg_cover": 18}},
        3: {"construct": {"dregs": 80, "topsoil": 80},
            "design": {"govern": 85, "ratio": 0.70, "dregs": 85, "topsoil": 80, "veg_restore": 85, "veg_cover": 14}},
    },
    "南方红壤区": {
        1: {"construct": {"dregs": 95, "topsoil": 92},
            "design": {"govern": 98, "ratio": 0.90, "dregs": 97, "topsoil": 92, "veg_restore": 98, "veg_cover": 25}},
        2: {"construct": {"dregs": 90, "topsoil": 87},
            "design": {"govern": 95, "ratio": 0.85, "dregs": 95, "topsoil": 87, "veg_restore": 95, "veg_cover": 22}},
        3: {"construct": {"dregs": 85, "topsoil": 82},
            "design": {"govern": 90, "ratio": 0.80, "dregs": 90, "topsoil": 82, "veg_restore": 90, "veg_cover": 19}},
    },
    "西南紫色土区": {
        1: {"construct": {"dregs": 90, "topsoil": 92},
            "design": {"govern": 97, "ratio": 0.85, "dregs": 92, "topsoil": 92, "veg_restore": 97, "veg_cover": 23}},
        2: {"construct": {"dregs": 85, "topsoil": 87},
            "design": {"govern": 94, "ratio": 0.80, "dregs": 88, "topsoil": 87, "veg_restore": 95, "veg_cover": 21}},
        3: {"construct": {"dregs": 80, "topsoil": 82},
            "design": {"govern": 89, "ratio": 0.75, "dregs": 84, "topsoil": 82, "veg_restore": 90, "veg_cover": 19}},
    },
    "西南岩溶区": {
        1: {"construct": {"dregs": 90, "topsoil": 95},
            "design": {"govern": 97, "ratio": 0.85, "dregs": 92, "topsoil": 95, "veg_restore": 96, "veg_cover": 21}},
        2: {"construct": {"dregs": 85, "topsoil": 90},
            "design": {"govern": 94, "ratio": 0.80, "dregs": 88, "topsoil": 90, "veg_restore": 94, "veg_cover": 19}},
        3: {"construct": {"dregs": 80, "topsoil": 85},
            "design": {"govern": 89, "ratio": 0.75, "dregs": 84, "topsoil": 85, "veg_restore": 89, "veg_cover": 17}},
    },
    "青藏高原区": {
        1: {"construct": {"dregs": 85, "topsoil": 90},
            "design": {"govern": 85, "ratio": 0.80, "dregs": 87, "topsoil": 90, "veg_restore": 95, "veg_cover": 16}},
        2: {"construct": {"dregs": 83, "topsoil": 85},
            "design": {"govern": 82, "ratio": 0.75, "dregs": 85, "topsoil": 85, "veg_restore": 90, "veg_cover": 13}},
        3: {"construct": {"dregs": 80, "topsoil": 80},
            "design": {"govern": 77, "ratio": 0.70, "dregs": 83, "topsoil": 80, "veg_restore": 85, "veg_cover": 10}},
    },
}


def show_table(region, level):
    t = TARGETS[region][level]
    print("== GB/T 50434-2018 表4.0.2  %s  防治标准等级：%d 级 ==" % (region, level))
    print("%-22s %-14s %-14s" % ("防治指标", "施工期", "设计水平年"))
    for k in ("govern", "ratio", "dregs", "topsoil", "veg_restore", "veg_cover"):
        c = t["construct"].get(k)
        d = t["design"].get(k)
        cs = ("%.2f" % c) if isinstance(c, float) else (str(c) if c is not None else "不作要求")
        ds = ("%.2f" % d) if isinstance(d, float) else (str(d) if d is not None else "不作要求")
        print("%-22s %-14s %-14s" % (IND_NAMES[k], cs, ds))
    if region == "北方风沙区":
        print("注：风沙区表土保护率不作要求；占地为耕地、园地时应剥离保护，据实确定。")


def main():
    ap = argparse.ArgumentParser(description="水土流失防治指标达标复核（GB/T 50434-2018）")
    ap.add_argument("--region", required=True, choices=REGIONS, help="水土保持区划（八区之一）")
    ap.add_argument("--level", type=int, required=True, choices=[1, 2, 3], help="防治标准等级")
    ap.add_argument("--period", default="design", choices=["construct", "design"],
                    help="时段：construct=施工期 / design=设计水平年（默认）")
    ap.add_argument("--show-table", action="store_true", help="只打印该区该等级限值表")
    # 实测指标（按需给）
    ap.add_argument("--governed", type=float, help="水土流失治理度(%%)")
    ap.add_argument("--ratio", type=float, help="土壤流失控制比")
    ap.add_argument("--dregs", type=float, help="渣土防护率(%%)")
    ap.add_argument("--topsoil", type=float, help="表土保护率(%%)")
    ap.add_argument("--veg-restore", type=float, help="林草植被恢复率(%%)")
    ap.add_argument("--veg-cover", type=float, help="林草覆盖率(%%)")
    # 调整情形
    ap.add_argument("--arid", choices=["extreme", "arid"], help="4.0.6 极干旱/干旱")
    ap.add_argument("--erosion", choices=["light", "moderate"], help="4.0.7 轻度/中度以上侵蚀")
    ap.add_argument("--terrain", choices=["mid", "high"], help="4.0.8 中山区/极高·高山区")
    ap.add_argument("--urban", action="store_true", help="4.0.9 城市区")
    ap.add_argument("--project-type", default="construct", choices=["construct", "productive"],
                    help="建设类 / 建设生产类（生产期指标另按 4.0.3，此处仅提示）")
    args = ap.parse_args()

    if args.show_table:
        show_table(args.region, args.level)
        return 0

    got = {"govern": args.governed, "ratio": args.ratio, "dregs": args.dregs,
           "topsoil": args.topsoil, "veg_restore": args.veg_restore, "veg_cover": args.veg_cover}
    if all(v is None for v in got.values()):
        print("参数不足：至少给一个指标实测值（--governed/--ratio/--dregs/--topsoil/--veg-restore/--veg-cover）")
        print("或加 --show-table 查看限值表。")
        return 2

    period = args.period
    pname = "施工期" if period == "construct" else "设计水平年"
    limits = TARGETS[args.region][args.level][period]
    print("== 防治指标达标复核（GB/T 50434-2018）==")
    print("区划=%s  等级=%d 级  时段=%s" % (args.region, args.level, pname))

    # 调整规则提示
    adj = []
    if args.arid == "extreme":
        adj.append("4.0.6-1 极干旱区：治理度可降 5%~8%，植被恢复率/覆盖率可不作定量要求")
    elif args.arid == "arid":
        adj.append("4.0.6-2 干旱区：治理度/植被恢复率/覆盖率可降 3%~5%")
    if args.erosion == "light":
        adj.append("4.0.7 轻度侵蚀为主：土壤流失控制比不应小于 1.0")
    elif args.erosion == "moderate":
        adj.append("4.0.7 中度以上侵蚀为主：控制比可降 0.1~0.2")
    if args.terrain == "mid":
        adj.append("4.0.8 中山区：渣土防护率可减 1%~3%")
    elif args.terrain == "high":
        adj.append("4.0.8 极高/高山区：渣土防护率可减 3%~5%")
    if args.urban:
        adj.append("4.0.9 城市区：渣土防护率、林草覆盖率可提高 1%~2%")
    if args.project_type == "productive":
        adj.append("4.0.3 建设生产类：生产期新增扰动范围指标 ≥ 施工期值，其他区域 ≥ 设计水平年值")
    if adj:
        print("-- 可适用调整情形 --")
        for a in adj:
            print("   * " + a)

    print("%-22s %-12s %-12s %s" % ("防治指标", "规范限值", "报告值", "判定"))
    print("-" * 62)
    all_pass = True
    any_checked = False
    for k in ("govern", "ratio", "dregs", "topsoil", "veg_restore", "veg_cover"):
        v = got[k]
        lim = limits.get(k)
        if v is None:
            continue
        any_checked = True
        if lim is None:
            # 表内无该项限值：北风沙区表土不作要求 / 施工期无该项
            note = "不作要求" if (k == "topsoil" and args.region == "北方风沙区") else "该时段不作要求"
            print("%-22s %-12s %-12s %s" % (IND_NAMES[k], note, "%.2f" % v if isinstance(v, float) else v, "[—]"))
            continue
        ok = v >= lim
        all_pass = all_pass and ok
        lim_s = "%.2f" % lim if isinstance(lim, float) else str(lim)
        val_s = "%.2f" % v if isinstance(v, float) else str(v)
        print("%-22s %-12s %-12s %s" % (IND_NAMES[k], "≥" + lim_s, val_s, "达标" if ok else "★不达标"))

    if not any_checked:
        print("未提供任何有意义的指标值。")
        return 2

    print("-" * 62)
    print("结论：%s" % ("全部达标" if all_pass else "存在不达标指标 → 防治目标未落实，属 ★/● 级问题"))
    print("依据：GB/T 50434-2018 表 4.0.2（区划+等级+时段）；调整情形见 4.0.5～4.0.10。")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
