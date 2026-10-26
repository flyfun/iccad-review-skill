#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""稳定与构造数值复核 —— 洪评报告"防洪工程安全影响 / 河势稳定"判据。

【判定依据】
  GB 50286-2013《堤防工程设计规范》
    表 3.2.1  安全加高值 A
    表 3.2.3  土堤边坡抗滑稳定安全系数
    表 3.2.5  防洪墙沿基底面抗滑稳定安全系数（岩基抗剪断 正常3.00/非常Ⅰ2.50/非常Ⅱ2.30）
    表 3.2.6  土基上防洪墙基底应力最大/最小值之比
    表 3.2.7  岩基上防洪墙抗倾覆稳定安全系数
    9.2.10    岩基上防洪墙基底不应出现拉应力
    7.2.4     黏性土土堤压实度（★强制性条文）
    7.2.5     无黏性土土堤相对密度（★强制性条文）
    13.2.2    护堤地宽度
  SL/T 386-2025《水利水电工程边坡与挡土墙设计规范》（替代 SL 386-2007 + SL 379-2007）
    表 3.3.7  边坡抗滑稳定安全系数
    表 3.4.5  土质地基挡墙抗滑；表 3.4.7 岩石地基挡墙抗滑（抗剪断 3.00/2.50/2.30）
    表 3.4.10、3.4.11 抗倾覆；表 3.4.12 空箱式抗浮
    表 7.4.6  基底应力比；正文 平均基底应力≤允许承载力、最大基底应力≤1.2×允许承载力
  GB 50707-2011《河道整治设计规范》
    表 8.2.5  防护工程稳定安全系数（坡式护岸抗滑 1.25/1.20；墙式抗滑 1.25/1.20、抗倾 1.50/1.40）

【模式】
  freeboard    安全加高 A 值 + 堤顶高程校核（GB 50286 表 3.2.1）
  slope        边坡抗滑稳定安全系数（GB 50286 表 3.2.3 / SL/T 386 表 3.3.7）
  wall-slide   挡墙/防洪墙沿基底面抗滑（GB 50286 表 3.2.5 / SL/T 386 表 3.4.5、3.4.7）
  overturning  抗倾覆（GB 50286 表 3.2.7 / SL/T 386 表 3.4.10、3.4.11）
  anti-float   空箱式挡墙抗浮（SL/T 386 表 3.4.12）
  base-stress  基底应力比 + 承载力/拉应力校核（GB 50286 表 3.2.6 / SL/T 386 表 7.4.6）
  compaction   压实度 / 相对密度（GB 50286 7.2.4、7.2.5 ★强条）
  berm         护堤地宽度（GB 50286 13.2.2）
  revetment    河道整治防护工程抗滑/抗倾（GB 50707 表 8.2.5）

【用法】
  python calc_stability.py --mode freeboard --levee-level 2 --overtopping 不允许 \
         --design-flood-level 12.30 --crest-elev 13.50
  python calc_stability.py --mode slope --spec gb50286 --level 2 --method 简化毕肖普法 \
         --condition 正常运用 --report 1.32
  python calc_stability.py --mode wall-slide --spec gb50286 --foundation 土基 --level 3 \
         --condition 正常运用 --report 1.22
  python calc_stability.py --mode base-stress --soil 中等坚实 --combo 基本组合 \
         --sigma-max 180 --sigma-min 85
  python calc_stability.py --mode compaction --soil 黏性土 --level 2 --height 8 --report 0.92
  python calc_stability.py --mode berm --level 1 --report 25

【退出码】0 = 满足；1 = 不满足（含违反强制性条文）；2 = 输入错误
"""
import argparse
import sys

LEVELS5 = [1, 2, 3, 4, 5]


def _i4(level):
    """4 列表格（1/2/3/4、5级）的列号。"""
    return 0 if level == 1 else 1 if level == 2 else 2 if level == 3 else 3


def _i5(level):
    """5 列表格（1~5级）的列号。"""
    return level - 1


def _i4_label(level):
    return "4、5级" if level >= 4 else "%d级" % level


# ---- GB 50286 表 3.2.1 安全加高值 A (m)：[1,2,3,4,5 级] ----
FREEBOARD = {
    "不允许越浪": [1.0, 0.8, 0.7, 0.6, 0.5],
    "允许越浪":   [0.5, 0.4, 0.4, 0.3, 0.3],
}

# ---- GB 50286 表 3.2.3 土堤边坡抗滑稳定安全系数 [1,2,3,4,5 级] ----
SLOPE_GB50286 = {
    ("瑞典圆弧法", "正常运用"):   [1.30, 1.25, 1.20, 1.15, 1.10],
    ("瑞典圆弧法", "非常运用Ⅰ"): [1.20, 1.15, 1.10, 1.05, 1.05],
    ("瑞典圆弧法", "非常运用Ⅱ"): [1.10, 1.05, 1.05, 1.00, 1.00],
    ("简化毕肖普法", "正常运用"):   [1.50, 1.35, 1.30, 1.25, 1.20],
    ("简化毕肖普法", "非常运用Ⅰ"): [1.30, 1.25, 1.20, 1.15, 1.10],
    ("简化毕肖普法", "非常运用Ⅱ"): [1.20, 1.15, 1.15, 1.10, 1.05],
}

# ---- SL/T 386 表 3.3.7 边坡抗滑（区间，取**下限**为最低要求）[1,2,3,4,5 级] ----
SLOPE_SL386 = {
    "正常运用":   [(1.30, 1.25), (1.25, 1.20), (1.20, 1.15), (1.15, 1.10), (1.10, 1.05)],
    "非常运用Ⅰ": [(1.25, 1.20), (1.20, 1.15), (1.15, 1.10), (1.10, 1.05), (1.10, 1.05)],
    "非常运用Ⅱ": [(1.15, 1.10), (1.10, 1.05), (1.10, 1.05), (1.05, 1.00), (1.05, 1.00)],
}

# ---- 抗滑：GB 50286 表 3.2.5 / SL/T 386 表 3.4.5、3.4.7 （4 列：1/2/3/4、5级）----
WALL_GB50286 = {
    ("岩基", "抗剪", "正常运用"):   [1.15, 1.10, 1.08, 1.05],
    ("岩基", "抗剪", "非常运用Ⅰ"): [1.05, 1.05, 1.03, 1.00],
    ("岩基", "抗剪", "非常运用Ⅱ"): [1.03, 1.03, 1.00, 1.00],
    ("土基", "抗剪", "正常运用"):   [1.35, 1.30, 1.25, 1.20],
    ("土基", "抗剪", "非常运用Ⅰ"): [1.20, 1.15, 1.10, 1.05],
    ("土基", "抗剪", "非常运用Ⅱ"): [1.10, 1.05, 1.05, 1.00],
}
WALL_SL386 = {
    ("土基", "抗剪", "正常运用"):   [1.35, 1.30, 1.25, 1.20],
    ("土基", "抗剪", "非常运用Ⅰ"): [1.20, 1.15, 1.10, 1.05],
    ("土基", "抗剪", "非常运用Ⅱ"): [1.10, 1.05, 1.05, 1.00],
    ("岩基", "抗剪", "正常运用"):   [1.10, 1.08, 1.08, 1.05],
    ("岩基", "抗剪", "非常运用Ⅰ"): [1.05, 1.03, 1.03, 1.00],
    ("岩基", "抗剪", "非常运用Ⅱ"): [1.00, 1.00, 1.00, 1.00],
}
# 岩基抗剪断（与级别无关）
SHEAR_FRACTURE = {"正常运用": 3.00, "非常运用Ⅰ": 2.50, "非常运用Ⅱ": 2.30}

# ---- 抗倾覆：GB 50286 表 3.2.7（5 列）/ SL/T 386 表 3.4.10（4 列）、3.4.11 ----
OVERTURN_GB50286 = {
    "正常运用":   [1.60, 1.55, 1.50, 1.45, 1.40],
    "非常运用Ⅰ": [1.50, 1.45, 1.40, 1.35, 1.30],
    "非常运用Ⅱ": [1.40, 1.35, 1.30, 1.25, 1.20],
}
OVERTURN_SL386_SOIL = {
    "正常运用":   [1.60, 1.50, 1.50, 1.40],
    "非常运用Ⅰ": [1.50, 1.40, 1.40, 1.30],
    "非常运用Ⅱ": [1.50, 1.40, 1.40, 1.30],
}

# ---- SL/T 386 表 3.4.12 空箱式抗浮 ----
ANTI_FLOAT = {"正常运用": 1.10, "非常运用Ⅰ": 1.05, "非常运用Ⅱ": 1.05}

# ---- GB 50286 表 3.2.6 / SL/T 386 表 7.4.6 基底应力比 ----
BASE_STRESS = {  # 土质: (基本组合, 特殊组合)
    "松软":   (1.50, 2.00),
    "中等坚实": (2.00, 2.50),
    "坚实":   (2.50, 3.00),
}

# ---- GB 50707 表 8.2.5 防护工程稳定安全系数 ----
REVETMENT = {
    ("坡式护岸", "抗滑", "正常运用"):   1.25,
    ("坡式护岸", "抗滑", "非常运用"):   1.20,
    ("墙式防护", "抗滑", "正常运用"):   1.25,
    ("墙式防护", "抗滑", "非常运用"):   1.20,
    ("墙式防护", "抗倾", "正常运用"):   1.50,
    ("墙式防护", "抗倾", "非常运用"):   1.40,
}

# ---- GB 50286 13.2.2 护堤地宽度 (m)：级别 → (下限, 上限) ----
BERM = {1: (20, 30), 2: (10, 20), 3: (5, 10), 4: (3, 5), 5: (3, 5)}

# ---- 别名 ----
ALIAS = {
    "不允许": "不允许越浪", "不允许越浪": "不允许越浪", "no": "不允许越浪",
    "允许": "允许越浪", "允许越浪": "允许越浪", "yes": "允许越浪",
    "正常": "正常运用", "正常运用": "正常运用",
    "非常Ⅰ": "非常运用Ⅰ", "非常运用Ⅰ": "非常运用Ⅰ", "Ⅰ": "非常运用Ⅰ",
    "非常Ⅱ": "非常运用Ⅱ", "非常运用Ⅱ": "非常运用Ⅱ", "Ⅱ": "非常运用Ⅱ",
    "非常": "非常运用Ⅰ",
    "岩基": "岩基", "岩石地基": "岩基", "土基": "土基", "土质地基": "土基",
    "抗剪": "抗剪", "抗剪断": "抗剪断",
    "黏性土": "黏性土", "粘性土": "黏性土", "无黏性土": "无黏性土", "无粘性土": "无黏性土",
    "基本组合": "基本组合", "特殊组合": "特殊组合", "基本": "基本组合", "特殊": "特殊组合",
    "坡式护岸": "坡式护岸", "坡式": "坡式护岸",
    "墙式防护": "墙式防护", "墙式": "墙式防护",
    "抗滑": "抗滑", "抗倾": "抗倾",
    "瑞典圆弧法": "瑞典圆弧法", "瑞典": "瑞典圆弧法",
    "简化毕肖普法": "简化毕肖普法", "毕肖普": "简化毕肖普法",
}
SPEC_ALIAS = {"gb50286": "gb50286", "GB50286": "gb50286", "50286": "gb50286",
              "sl386": "sl386", "SL386": "sl386", "386": "sl386",
              "gb50707": "gb50707", "50707": "gb50707"}


def _ali(v):
    if v is None:
        return None
    return ALIAS.get(v, ALIAS.get(v.strip(), v.strip()))


def _check_min(label, actual, need, bad, fmt="%.2f", note=""):
    ok = actual + 1e-9 >= need
    print("%s : %s     规范限值 : ≥ %s    %s" % (label, fmt % actual, fmt % need, note))
    if ok:
        print("  判定：满足")
    else:
        print("  ★ 判定：不满足 —— 缺口 %s" % (fmt % (need - actual)))
        bad.append("%s %s < 限值 %s" % (label, fmt % actual, fmt % need))
    return ok


def _check_report_min(label, report, need, bad, fmt="%.3f", ci=False, note=""):
    """报告给出的安全系数/比值 与规范限值比对。ci=True → 不满足即违反强制性条文。"""
    if report is None:
        print("（未给报告值，仅给出规范限值 %s；如需判定请传 --report）" % (fmt % need))
        return None
    ok = report + 1e-9 >= need
    print("-" * 60)
    print("报告给出%s : %s     规范限值 : ≥ %s    %s" % (label, fmt % report, fmt % need, note))
    if ok:
        print("  判定：满足")
    else:
        tag = "★ **违反强制性条文**" if ci else "★ 判定：不满足"
        print("  %s —— 报告值 %s < 限值 %s，缺口 %s" % (tag, fmt % report, fmt % need, fmt % (need - report)))
        bad.append("%s %s < 限值 %s" % (label, fmt % report, fmt % need))
    return ok


def _check_max(label, actual, lim, bad, fmt="%.2f", note=""):
    """上限型判据（如基底应力比 σmax/σmin ≤ 表值）。"""
    ok = actual - 1e-9 <= lim
    print("%s : %s     规范限值 : ≤ %s    %s" % (label, fmt % actual, fmt % lim, note))
    if ok:
        print("  判定：满足")
    else:
        print("  ★ 判定：不满足 —— 超出 %s" % (fmt % (actual - lim)))
        bad.append("%s %s > 限值 %s" % (label, fmt % actual, fmt % lim))
    return ok


def _check_report_max(label, report, lim, bad, fmt="%.2f", note=""):
    """报告值 vs 上限型规范限值。"""
    if report is None:
        print("（未给报告值，仅给出规范限值 %s；如需判定请传 --report）" % (fmt % lim))
        return None
    ok = report - 1e-9 <= lim
    print("-" * 60)
    print("报告给出%s : %s     规范限值 : ≤ %s    %s" % (label, fmt % report, fmt % lim, note))
    if ok:
        print("  判定：满足")
    else:
        print("  ★ 判定：不满足 —— 报告值 %s > 限值 %s，超出 %s"
              % (fmt % report, fmt % lim, fmt % (report - lim)))
        bad.append("%s %s > 限值 %s" % (label, fmt % report, fmt % lim))
    return ok


def main():
    ap = argparse.ArgumentParser(description="稳定与构造数值复核（GB 50286 / SL/T 386 / GB 50707）")
    ap.add_argument("--mode", required=True,
                    choices=["freeboard", "slope", "wall-slide", "overturning",
                             "anti-float", "base-stress", "compaction", "berm", "revetment"])
    ap.add_argument("--spec", default=None, help="[slope/wall-slide] gb50286 / sl386")
    ap.add_argument("--level", type=int, default=None, help="建筑物/堤防级别 1~5")
    ap.add_argument("--levee-level", type=int, default=None, help="[freeboard] 堤防级别 1~5")
    ap.add_argument("--method", default=None, help="[slope] 瑞典圆弧法 / 简化毕肖普法（GB 50286）")
    ap.add_argument("--condition", default=None, help="运用条件：正常运用 / 非常运用Ⅰ / 非常运用Ⅱ")
    ap.add_argument("--foundation", default=None, help="[wall-slide/overturning] 岩基 / 土基")
    ap.add_argument("--formula", default=None, help="[wall-slide] 抗剪 / 抗剪断")
    ap.add_argument("--overtopping", default=None, help="[freeboard] 不允许越浪 / 允许越浪")
    ap.add_argument("--design-flood-level", type=float, default=None, help="[freeboard] 设计洪水位 (m)")
    ap.add_argument("--crest-elev", type=float, default=None, help="[freeboard] 堤顶高程 (m)")
    ap.add_argument("--wave-runup", type=float, default=None, help="[freeboard] 波浪爬高 R (m)，可选")
    ap.add_argument("--soil", default=None, help="[base-stress] 松软/中等坚实/坚实；[compaction] 黏性土/无黏性土")
    ap.add_argument("--combo", default=None, help="[base-stress] 基本组合 / 特殊组合")
    ap.add_argument("--sigma-max", type=float, default=None, help="[base-stress] 最大基底应力 (kPa)")
    ap.add_argument("--sigma-min", type=float, default=None, help="[base-stress] 最小基底应力 (kPa)")
    ap.add_argument("--allow-bearing", type=float, default=None, help="[base-stress] 地基允许承载力 (kPa)")
    ap.add_argument("--height", type=float, default=None, help="[compaction] 堤身高度 (m)")
    ap.add_argument("--type", dest="rtype", default=None, help="[revetment] 坡式护岸 / 墙式防护")
    ap.add_argument("--check", dest="checkwhat", default=None, help="[revetment] 抗滑 / 抗倾")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的安全系数/比值/压实度/宽度，用于比对")
    args = ap.parse_args()

    print("=" * 60)
    print("稳定与构造数值复核（GB 50286 / SL/T 386 / GB 50707）")
    print("=" * 60)
    bad = []

    # ---------------- freeboard ----------------
    if args.mode == "freeboard":
        lv = args.levee_level or args.level
        if lv is None or lv not in LEVELS5:
            print("输入错误：freeboard 需 --levee-level 1~5", file=sys.stderr)
            return 2
        over = _ali(args.overtopping) or "不允许越浪"
        if over not in FREEBOARD:
            print("输入错误：--overtopping 取 不允许越浪 / 允许越浪", file=sys.stderr)
            return 2
        need = FREEBOARD[over][_i5(lv)]
        print("依据               : GB 50286-2013 表 3.2.1 安全加高值 A")
        print("堤防级别 / 越浪条件 : %d 级 / %s" % (lv, over))
        _check_min("安全加高 A", need, need, bad, "%.2f", "（表 3.2.1 取值）")
        if args.design_flood_level is not None and args.crest_elev is not None:
            runup = args.wave_runup or 0.0
            req = args.design_flood_level + need + runup
            act = args.crest_elev
            print("-" * 60)
            print("设计洪水位         : %.2f m" % args.design_flood_level)
            if runup:
                print("波浪爬高 R         : %.2f m" % runup)
            print("要求堤顶高程       : %.2f + %.2f%s = %.2f m"
                  % (args.design_flood_level, need, (" + %.2f" % runup) if runup else "", req))
            print("报告堤顶高程       : %.2f m" % act)
            _check_min("堤顶高程", act, req, bad, "%.2f", "（设计洪水位 + A + R）")
        elif args.crest_elev is not None or args.design_flood_level is not None:
            print("（堤顶高程校核需同时给 --design-flood-level 与 --crest-elev）")

    # ---------------- slope ----------------
    elif args.mode == "slope":
        lv = args.level
        if lv is None or lv not in LEVELS5:
            print("输入错误：slope 需 --level 1~5", file=sys.stderr)
            return 2
        spec = SPEC_ALIAS.get(args.spec or "gb50286", args.spec)
        cond = _ali(args.condition) or "正常运用"
        if spec == "gb50286":
            method = _ali(args.method) or "瑞典圆弧法"
            key = (method, cond)
            if key not in SLOPE_GB50286:
                print("输入错误：方法/运用条件不在表 3.2.3 中（%s/%s）" % (method, cond), file=sys.stderr)
                return 2
            tbl = SLOPE_GB50286[key]
            print("依据               : GB 50286-2013 表 3.2.3 土堤边坡抗滑稳定安全系数")
            print("方法 / 运用条件    : %s / %s" % (method, cond))
            note = ""
        elif spec == "sl386":
            if cond not in SLOPE_SL386:
                print("输入错误：运用条件不在表 3.3.7 中（%s）" % cond, file=sys.stderr)
                return 2
            hi, lo = SLOPE_SL386[cond][_i5(lv)]
            print("依据               : SL/T 386-2025 表 3.3.7 边坡抗滑稳定安全系数")
            print("运用条件           : %s" % cond)
            print("规范区间           : %.2f ~ %.2f（表 3.3.7 给区间；按**下限 %.2f** 作最低要求，"
                  "取上限 %.2f 的情形须说明所用计算方法）" % (lo, hi, lo, hi))
            tbl, note = [lo] * 5, "（区间下限 %.2f，上限 %.2f）" % (lo, hi)
        else:
            print("输入错误：--spec 取 gb50286 / sl386", file=sys.stderr)
            return 2
        print("建筑物级别         : %d 级" % lv)
        need = tbl[_i5(lv)]
        _check_report_min("边坡抗滑安全系数 K", args.report, need, bad, "%.3f", note=note)

    # ---------------- wall-slide ----------------
    elif args.mode == "wall-slide":
        lv = args.level
        if lv is None or lv not in LEVELS5:
            print("输入错误：wall-slide 需 --level 1~5", file=sys.stderr)
            return 2
        spec = SPEC_ALIAS.get(args.spec or "gb50286", args.spec)
        fnd = _ali(args.foundation)
        cond = _ali(args.condition) or "正常运用"
        fm = _ali(args.formula) or "抗剪"
        if fnd not in ("岩基", "土基"):
            print("输入错误：wall-slide 需 --foundation 岩基 / 土基", file=sys.stderr)
            return 2
        if fm == "抗剪断":
            if fnd != "岩基":
                print("输入错误：抗剪断公式仅用于岩基上防洪墙", file=sys.stderr)
                return 2
            if cond not in SHEAR_FRACTURE:
                print("输入错误：--condition 取 正常运用/非常运用Ⅰ/非常运用Ⅱ", file=sys.stderr)
                return 2
            need = SHEAR_FRACTURE[cond]
            src = "GB 50286-2013 表 3.2.5 / SL/T 386-2025 表 3.4.7（岩基按抗剪断公式）"
        else:
            tbl = WALL_GB50286 if spec == "gb50286" else WALL_SL386 if spec == "sl386" else None
            if tbl is None:
                print("输入错误：--spec 取 gb50286 / sl386", file=sys.stderr)
                return 2
            key = (fnd, "抗剪", cond)
            if key not in tbl:
                print("输入错误：地基/运用条件不在表中（%s/%s）" % (fnd, cond), file=sys.stderr)
                return 2
            need = tbl[key][_i4(lv)]
            src = ("GB 50286-2013 表 3.2.5 防洪墙沿基底面抗滑稳定安全系数"
                   if spec == "gb50286" else
                   "SL/T 386-2025 表 3.4.5（土基）/ 表 3.4.7（岩基）挡墙抗滑")
        print("依据               : %s" % src)
        print("地基 / 级别 / 条件  : %s / %d 级%s / %s" % (fnd, lv, _i4_label(lv) if lv >= 4 else "", cond))
        print("计算式             : %s" % fm)
        _check_report_min("抗滑安全系数 K", args.report, need, bad, "%.3f")

    # ---------------- overturning ----------------
    elif args.mode == "overturning":
        lv = args.level
        if lv is None or lv not in LEVELS5:
            print("输入错误：overturning 需 --level 1~5", file=sys.stderr)
            return 2
        spec = SPEC_ALIAS.get(args.spec or "gb50286", args.spec)
        fnd = _ali(args.foundation) or "岩基"
        cond = _ali(args.condition) or "正常运用"
        if spec == "gb50286":
            if cond not in OVERTURN_GB50286:
                print("输入错误：--condition 取 正常运用/非常运用Ⅰ/非常运用Ⅱ", file=sys.stderr)
                return 2
            need = OVERTURN_GB50286[cond][_i5(lv)]
            src = "GB 50286-2013 表 3.2.7 岩基上防洪墙抗倾覆稳定安全系数"
        elif spec == "sl386":
            if fnd == "土基":
                if cond not in OVERTURN_SL386_SOIL:
                    print("输入错误：--condition 取 正常运用/非常运用Ⅰ/非常运用Ⅱ", file=sys.stderr)
                    return 2
                need = OVERTURN_SL386_SOIL[cond][_i4(lv)]
                src = "SL/T 386-2025 表 3.4.10 土质地基挡墙抗倾覆"
            else:
                normal = (lv <= 3)
                need = 1.50 if normal else 1.40
                if cond != "正常运用":
                    need = 1.30
                src = "SL/T 386-2025 表 3.4.11 岩石地基挡墙抗倾覆（1/2/3级正常1.50、4/5级正常1.40，非常1.30）"
        else:
            print("输入错误：--spec 取 gb50286 / sl386", file=sys.stderr)
            return 2
        print("依据               : %s" % src)
        print("地基 / 级别 / 条件  : %s / %d 级 / %s" % (fnd, lv, cond))
        _check_report_min("抗倾覆安全系数 K", args.report, need, bad, "%.3f")

    # ---------------- anti-float ----------------
    elif args.mode == "anti-float":
        cond = _ali(args.condition) or "正常运用"
        if cond not in ANTI_FLOAT:
            print("输入错误：--condition 取 正常运用/非常运用Ⅰ/非常运用Ⅱ", file=sys.stderr)
            return 2
        need = ANTI_FLOAT[cond]
        print("依据               : SL/T 386-2025 表 3.4.12 空箱式挡土墙抗浮稳定安全系数")
        print("运用条件           : %s" % cond)
        _check_report_min("抗浮安全系数 K", args.report, need, bad, "%.3f")

    # ---------------- base-stress ----------------
    elif args.mode == "base-stress":
        soil = _ali(args.soil)
        combo = _ali(args.combo) or "基本组合"
        if soil not in BASE_STRESS:
            print("输入错误：--soil 取 松软 / 中等坚实 / 坚实", file=sys.stderr)
            return 2
        if combo not in ("基本组合", "特殊组合"):
            print("输入错误：--combo 取 基本组合 / 特殊组合", file=sys.stderr)
            return 2
        lim = BASE_STRESS[soil][0 if combo == "基本组合" else 1]
        print("依据               : GB 50286-2013 表 3.2.6 / SL/T 386-2025 表 7.4.6 基底应力比")
        print("判据方向           : **上限型** —— σmax/σmin 不得大于表值（限制基底应力不均匀）")
        print("地基土质 / 组合    : %s / %s" % (soil, combo))
        if args.sigma_max is not None and args.sigma_min is not None:
            if args.sigma_min <= 0:
                print("σmax / σmin        : %.2f / %.2f kPa" % (args.sigma_max, args.sigma_min))
                print("  ★ 判定：不满足 —— 基底出现拉应力（GB 50286 9.2.10：岩基上防洪墙基底不应出现拉应力）")
                bad.append("基底出现拉应力（σmin %.2f kPa ≤ 0）" % args.sigma_min)
            else:
                ratio = args.sigma_max / args.sigma_min
                print("σmax / σmin        : %.2f / %.2f kPa" % (args.sigma_max, args.sigma_min))
                _check_max("基底应力比 σmax/σmin", ratio, lim, bad, "%.2f")
        elif args.report is not None:
            _check_report_max("基底应力比 σmax/σmin", args.report, lim, bad, "%.2f")
        else:
            print("（未给 σmax/σmin，仅列限值：基底应力比 ≤ %.2f）" % lim)
        if args.allow_bearing is not None and args.sigma_max is not None:
            print("-" * 60)
            print("地基允许承载力     : %.2f kPa" % args.allow_bearing)
            _check_max("最大基底应力 σmax", args.sigma_max, args.allow_bearing, bad, "%.2f",
                       "（SL/T 386 7.4.6：σmax ≤ 允许承载力）")
            _check_max("σmax vs 1.2×允许承载力", args.sigma_max, 1.2 * args.allow_bearing, bad, "%.2f",
                       "（SL/T 386 7.4.6：σmax ≤ 1.2×允许承载力）")

    # ---------------- compaction ----------------
    elif args.mode == "compaction":
        soil = _ali(args.soil)
        lv = args.level
        if soil not in ("黏性土", "无黏性土") or lv is None or lv not in LEVELS5:
            print("输入错误：compaction 需 --soil 黏性土/无黏性土 与 --level 1~5", file=sys.stderr)
            return 2
        h = args.height
        if soil == "黏性土":
            if lv == 1:
                need, why = 0.95, "1 级 ≥0.95"
            elif lv == 2:
                need, why = 0.93, "2 级 ≥0.93"
            elif lv == 3:
                if h is not None and h >= 6:
                    need, why = 0.93, "堤身高度≥6m 的 3 级 ≥0.93"
                else:
                    need, why = 0.91, "堤身高度<6m 的 3 级及以下 ≥0.91"
            else:
                need, why = 0.91, "堤身高度<6m 的 3 级及以下 ≥0.91"
            unit, label = "压实度", "压实度"
            src = "GB 50286-2013 7.2.4（★强制性条文）"
        else:
            if lv in (1, 2):
                need, why = 0.65, "1、2 级 ≥0.65"
            elif lv == 3:
                if h is not None and h >= 6:
                    need, why = 0.65, "堤身高度≥6m 的 3 级 ≥0.65"
                else:
                    need, why = 0.60, "堤身高度<6m 的 3 级及以下 ≥0.60"
            else:
                need, why = 0.60, "堤身高度<6m 的 3 级及以下 ≥0.60"
            unit, label = "相对密度", "相对密度 Dr"
            src = "GB 50286-2013 7.2.5（★强制性条文）"
        print("依据               : %s" % src)
        print("土类 / 级别%s      : %s / %d 级%s"
              % (" / 堤身高度" if h is not None else "", soil, lv, ("（%.1f m）" % h) if h is not None else ""))
        print("取值规则           : %s" % why)
        _check_report_min(label, args.report, need, bad, "%.3f", ci=True,
                          note="（★ 强制性条文，不满足即违反强条）")

    # ---------------- berm ----------------
    elif args.mode == "berm":
        lv = args.level
        if lv is None or lv not in LEVELS5:
            print("输入错误：berm 需 --level 1~5", file=sys.stderr)
            return 2
        lo, hi = BERM[lv]
        print("依据               : GB 50286-2013 13.2.2 护堤地宽度（背水侧）")
        print("堤防级别           : %d 级" % lv)
        print("规范取值           : %d ~ %d m" % (lo, hi))
        if args.report is not None:
            ok = (args.report + 1e-9 >= lo) and (args.report - 1e-9 <= hi)
            print("-" * 60)
            print("报告取用护堤地宽度 : %.1f m" % args.report)
            if ok:
                print("  判定：满足（在规范区间内）")
            else:
                print("  ★ 判定：不满足 —— 超出 %d~%d m 区间" % (lo, hi))
                bad.append("护堤地宽度 %.1f m 不在 %d~%d m 区间" % (args.report, lo, hi))
        else:
            print("（未给报告值，仅列规范区间；如需判定请传 --report）")

    # ---------------- revetment ----------------
    else:
        rt = _ali(args.rtype)
        cw = _ali(args.checkwhat) or "抗滑"
        cond = _ali(args.condition) or "正常运用"
        cond2 = "正常运用" if cond == "正常运用" else "非常运用"
        if rt is None or (rt, cw, cond2) not in REVETMENT:
            print("输入错误：revetment 需 --type 坡式护岸/墙式防护 --check 抗滑/抗倾；"
                  "坡式护岸仅抗滑", file=sys.stderr)
            return 2
        need = REVETMENT[(rt, cw, cond2)]
        print("依据               : GB 50707-2011 表 8.2.5 防护工程稳定安全系数")
        print("型式 / 项目 / 条件  : %s / %s / %s" % (rt, cw, cond2))
        _check_report_min("%s安全系数 K" % cw, args.report, need, bad, "%.3f")

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
