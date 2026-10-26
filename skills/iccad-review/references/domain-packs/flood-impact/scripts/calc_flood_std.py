#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""防洪标准 / 堤防级别核定与符合性判定 —— 洪评"防洪标准和有关技术要求评价"(7.3) 用。

【判定依据】
  《防洪标准》GB 50201-2014
      表 3.0.1  城镇防护等级与防洪标准
      表 4.1.1  乡村防护区等级与防洪标准
      表 5.0.1  工矿企业防护等级与防洪标准
      **11.8.3（★强制性条文）** 堤防工程上的闸、涵、泵站等建筑物及其他构筑物的
                设计防洪标准，不应低于堤防工程的防洪标准，并应留有安全裕度。
  《水利水电工程等级划分及洪水标准》SL 252-2017
      表 4.4.1  防洪标准 → 堤防永久性水工建筑物级别
                （≥100→1级；<100,≥50→2；<50,≥30→3；<30,≥20→4；<20,≥10→5）
  SL/T 808-2025
      5.3.2-2  穿河、穿堤建设项目的设计防洪标准，**不应低于**穿越处河道及堤防防洪标准。
      5.5.2    蓄滞洪区内非防洪建设项目应符合洪水调度安排、满足……蓄滞洪区运用预案要求。
      6.1.2    计算工况应含所在河道现状及规划防洪标准对应工况、项目设计防洪标准对应工况。
      7.3.2    评价项目是否符合所在河道防洪标准、排涝标准及有关技术要求，
               防御洪涝的设防标准与措施是否适当，**是否为防洪标准提高所需治理工程留有空间**。

【模式】
    object       防护对象 → GB 50201 建议防洪标准（城镇/乡村/工矿企业）
    levee-level  防洪标准(重现期) → 堤防级别（SL 252 表 4.4.1）
    check        项目设计防洪标准 vs 所在河段/堤防防洪标准 → 符合性判定

【用法】
    python calc_flood_std.py --mode object --object city --population 120
    python calc_flood_std.py --mode object --object industry --scale 大型
    python calc_flood_std.py --mode levee-level --flood-std 50
    python calc_flood_std.py --mode check --project-std 50 --reach-std 100
    python calc_flood_std.py --mode check --project-std 50 --levee-level 2 --has-gate

【退出码】0 = 满足；1 = 不满足（标准偏低）；2 = 输入错误
"""
import argparse
import sys

# GB 50201-2014 表 3.0.1 城镇（常住人口 / 当量经济规模：万人）
CITY = [
    ("Ⅰ", "特别重要", 150.0, 300.0, "≥200"),
    ("Ⅱ", "重要",     50.0, 100.0, "200~100"),
    ("Ⅲ", "比较重要", 20.0,  40.0, "100~50"),
    ("Ⅳ", "一般",      0.0,   0.0, "50~20"),
]
# GB 50201-2014 表 4.1.1 乡村（人口/万亩、耕地/万亩）
RURAL = [
    ("Ⅰ", 150.0, 300.0, "100~50"),
    ("Ⅱ",  50.0, 100.0, "50~30"),
    ("Ⅲ",  20.0,  30.0, "30~20"),
    ("Ⅳ",   0.0,   0.0, "20~10"),
]
# GB 50201-2014 表 5.0.1 工矿企业
INDUSTRY = {
    "特大型": ("Ⅰ", "200~100"),
    "大型":   ("Ⅱ", "100~50"),
    "中型":   ("Ⅲ", "50~20"),
    "小型":   ("Ⅳ", "20~10"),
}


def levee_level(std):
    """SL 252-2017 表 4.4.1：防洪标准(重现期 年) → 堤防级别。"""
    if std >= 100:
        return 1
    if std >= 50:
        return 2
    if std >= 30:
        return 3
    if std >= 20:
        return 4
    if std >= 10:
        return 5
    return None


def main():
    ap = argparse.ArgumentParser(description="防洪标准 / 堤防级别核定（GB 50201-2014、SL 252-2017）")
    ap.add_argument("--mode", required=True, choices=["object", "levee-level", "check"])
    ap.add_argument("--object", default=None, choices=["city", "rural", "industry"], help="[object] 防护对象类别")
    ap.add_argument("--grade", default=None, help="[object] 防护等级 Ⅰ/Ⅱ/Ⅲ/Ⅳ")
    ap.add_argument("--population", type=float, default=None, help="[object] 常住人口/人口 (万人)")
    ap.add_argument("--economy", type=float, default=None, help="[object city] 当量经济规模 (万人)")
    ap.add_argument("--farmland", type=float, default=None, help="[object rural] 耕地面积 (万亩)")
    ap.add_argument("--scale", default=None, help="[object industry] 工矿企业规模：特大型/大型/中型/小型")
    ap.add_argument("--flood-std", type=float, default=None, help="[levee-level] 防洪标准重现期 (年)")
    ap.add_argument("--project-std", type=float, default=None, help="[check] 项目设计防洪标准 (年)")
    ap.add_argument("--reach-std", type=float, default=None, help="[check] 所在河段(河道)防洪标准 (年)")
    ap.add_argument("--levee-level", type=int, default=None, help="[check] 穿越处堤防级别 1~5")
    ap.add_argument("--has-gate", action="store_true", help="[check] 项目含堤防上的闸/涵/泵站等建筑物（触发 GB 50201 11.8.3 强条）")
    args = ap.parse_args()

    print("=" * 60)

    if args.mode == "object":
        if args.object == "city":
            print("城镇防洪标准核定（GB 50201-2014 表 3.0.1）")
            print("=" * 60)
            grade = args.grade
            if grade is None:
                p = args.population if args.population is not None else -1
                e = args.economy if args.economy is not None else -1
                for g, imp, pp, ee, rng in CITY:
                    if p >= pp or e >= ee:
                        grade = g
                        break
                if grade is None:
                    print("输入错误：须给 --grade，或给 --population / --economy 以便定级", file=sys.stderr)
                    return 2
            row = next((r for r in CITY if r[0] == grade), None)
            if row is None:
                print("输入错误：--grade 须为 Ⅰ/Ⅱ/Ⅲ/Ⅳ", file=sys.stderr)
                return 2
            print("防护等级           : %s（%s）" % (row[0], row[1]))
            print("建议防洪标准       : %s 年一遇" % row[4])
            print("依据               : GB 50201-2014 表 3.0.1")
        elif args.object == "rural":
            print("乡村防护区防洪标准核定（GB 50201-2014 表 4.1.1）")
            print("=" * 60)
            grade = args.grade
            if grade is None:
                p = args.population if args.population is not None else -1
                f = args.farmland if args.farmland is not None else -1
                for g, pp, ff, rng in RURAL:
                    if p >= pp or f >= ff:
                        grade = g
                        break
                if grade is None:
                    print("输入错误：须给 --grade，或给 --population / --farmland 以便定级", file=sys.stderr)
                    return 2
            row = next((r for r in RURAL if r[0] == grade), None)
            if row is None:
                print("输入错误：--grade 须为 Ⅰ/Ⅱ/Ⅲ/Ⅳ", file=sys.stderr)
                return 2
            print("防护等级           : %s" % row[0])
            print("建议防洪标准       : %s 年一遇" % row[3])
            print("依据               : GB 50201-2014 表 4.1.1")
        else:
            print("工矿企业防洪标准核定（GB 50201-2014 表 5.0.1）")
            print("=" * 60)
            if args.scale not in INDUSTRY:
                print("输入错误：--scale 须为 特大型/大型/中型/小型", file=sys.stderr)
                return 2
            g, rng = INDUSTRY[args.scale]
            print("企业规模           : %s" % args.scale)
            print("防护等级           : %s" % g)
            print("建议防洪标准       : %s 年一遇" % rng)
            print("依据               : GB 50201-2014 表 5.0.1")
        print("=" * 60)
        print("注：表 5.0.1 另规定——当工矿企业遭淹后可能爆炸或致毒液毒气放射性大量泄漏时，")
        print("    中小型取 Ⅰ 等、特大/大型取 Ⅰ 等上限并采取专门防护措施；核工业应高于 200 年一遇。")
        return 0

    if args.mode == "levee-level":
        if args.flood_std is None:
            print("输入错误：levee-level 需 --flood-std", file=sys.stderr)
            return 2
        print("堤防级别核定（SL 252-2017 表 4.4.1）")
        print("=" * 60)
        lv = levee_level(args.flood_std)
        print("防洪标准           : %g 年一遇" % args.flood_std)
        if lv is None:
            print("★ 防洪标准低于 10 年一遇，未落入表 4.4.1 范围，须核对标准取值。")
            print("=" * 60)
            return 1
        print("堤防级别           : %d 级" % lv)
        print("对应 GB 50286 表号 : 3.1.3（堤防工程的级别）")
        print("=" * 60)
        print("注：当经批准的流域、区域防洪规划另有规定时，按其规定执行（SL 252-2017 4.4.1）。")
        return 0

    # check
    print("防洪标准符合性判定（SL/T 808-2025 5.3.2-2 / GB 50201-2014 11.8.3）")
    print("=" * 60)
    if args.project_std is None:
        print("输入错误：check 需 --project-std", file=sys.stderr)
        return 2
    if args.reach_std is None and args.levee_level is None:
        print("输入错误：check 需 --reach-std 或 --levee-level 之一作为比较基准", file=sys.stderr)
        return 2
    print("项目设计防洪标准   : %g 年一遇" % args.project_std)
    bad = []
    if args.reach_std is not None:
        print("所在河段防洪标准   : %g 年一遇" % args.reach_std)
        if args.project_std + 1e-9 >= args.reach_std:
            print("  判定(5.3.2-2)：满足 —— 项目标准不低于穿越处河道防洪标准")
        else:
            print("  ★ 判定(5.3.2-2)：不满足 —— 项目标准 %.0f 年 < 河道 %.0f 年"
                  % (args.project_std, args.reach_std))
            bad.append("项目标准 %.0f 年 < 河道 %.0f 年" % (args.project_std, args.reach_std))
    if args.levee_level is not None:
        if args.levee_level not in (1, 2, 3, 4, 5):
            print("输入错误：--levee-level 须为 1~5", file=sys.stderr)
            return 2
        need = {1: 100, 2: 50, 3: 30, 4: 20, 5: 10}[args.levee_level]
        print("穿越处堤防级别     : %d 级（对应防洪标准下限 %d 年一遇）" % (args.levee_level, need))
        if args.project_std + 1e-9 >= need:
            print("  判定(5.3.2-2)：满足 —— 项目标准不低于穿越处堤防防洪标准")
        else:
            print("  ★ 判定(5.3.2-2)：不满足 —— 项目标准 %.0f 年 < 堤防对应下限 %.0f 年"
                  % (args.project_std, need))
            bad.append("项目标准 %.0f 年 < 堤防下限 %.0f 年" % (args.project_std, need))
    if args.has_gate:
        print("-" * 60)
        if args.levee_level is not None:
            need = {1: 100, 2: 50, 3: 30, 4: 20, 5: 10}[args.levee_level]
            # 11.8.3 要求"不应低于……并应留有安全裕度"→ 必须严格高于堤防防洪标准
            if args.project_std > need:
                print("  判定(GB 50201 11.8.3 ★强条)：满足 —— 堤防上闸/涵/泵站设计防洪标准"
                      "（%.0f 年）高于堤防标准（%.0f 年），留有安全裕度"
                      % (args.project_std, need))
            else:
                print("  ★ 判定(GB 50201 11.8.3 ★强条)：**违反强制性条文** —— 堤防上的闸、涵、"
                      "泵站等建筑物及其他构筑物的设计防洪标准，不应低于堤防工程的防洪标准，"
                      "并应留有安全裕度（当前 %.0f 年 未高于堤防 %.0f 年，无安全裕度）"
                      % (args.project_std, need))
                bad.append("违反 GB 50201-2014 11.8.3（强条）：堤防上建筑物未留安全裕度")
        else:
            print("  提示：已勾选含堤防上闸/涵/泵站，但未给 --levee-level，无法核 GB 50201 11.8.3 强条。")
    print("-" * 60)
    if bad:
        print("★ 结论：不满足 —— " + "；".join(bad))
        print("=" * 60)
        return 1
    print("结论：满足（就本次给定基准而言）")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
