#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泵房稳定复核（泵站工程报告审查用）。

【它解决什么】
    泵房抗滑、抗浮、基底应力、镇墩稳定是泵站安全的硬指标，且**强条密集**（7.3.5 / 7.3.8）。
    报告常：分级别套错抗滑栏、把抗浮按级别分档、把"不均匀系数"当"越大越好"、
    或把地震荷载与校核运用水位组合。本工具按 GB 50265 独立比对。

【依据】
    GB 50265-2022：
      7.3.5 ★ 泵房沿基础底面抗滑稳定安全系数允许值（表 7.3.5：地基类别 × 荷载组合 × 级别）
      7.3.7 / 7.3.8 ★ 抗浮 K = ∑G/∑U，不分级别与地基，基本 ≥1.10、特殊 ≥1.05
      7.3.3   荷载组合（地震荷载不应与校核运用水位组合）
      7.4 节  基底应力不均匀系数允许值（**上限型**：松软 1.5/2.0、中等坚实 2.0/2.5、坚实 2.5/3.0）
      8.3.11  镇墩抗滑 1.30/1.10、抗倾 1.50/1.20

【判据方向】
    抗滑/抗浮/抗倾 → **下限型**（K 应 ≥ 允许值）
    基底应力不均匀系数 → **上限型**（σmax/σmin 应 ≤ 允许值）

【用法】
    python calc_stability.py --mode slide --foundation 土基 --combo 基本 --level 3 --k 1.28
    python calc_stability.py --mode slide --foundation 岩基 --combo 特殊I --level 1 --formula 抗剪断 --k 2.6
    python calc_stability.py --mode uplift --combo 基本 --k 1.15
    python calc_stability.py --mode bearing --soil 中等坚实 --combo 基本 --sigma-max 180 --sigma-min 85
    python calc_stability.py --mode pier --type 抗倾 --combo 基本 --resisting 950 --driving 600

【退出码】统一语义（家族约定，勿改）
    0 = 满足 · 1 = 不满足（含违反强条）· 2 = 输入错 · 3 = 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— GB 50265 表 7.3.5 抗滑允许值：地基 → 组合 → {级别: 值} ——
SLIDE = {
    "土基": {
        "基本": {1: 1.35, 2: 1.30, 3: 1.25, "4,5": 1.20},
        "特殊I": {1: 1.20, 2: 1.15, 3: 1.10, "4,5": 1.05},
        "特殊II": {1: 1.10, 2: 1.05, 3: 1.05, "4,5": 1.00},
    },
    "岩基": {
        "基本": {1: 1.10, 2: 1.08, 3: 1.05},
        "特殊I": {1: 1.05, 2: 1.03, 3: 1.00},
        "特殊II": {1: 1.00},
    },
    "岩基抗剪断": {"基本": 3.00, "特殊I": 2.50, "特殊II": 2.30},   # 不分级别
}
# —— 7.3.8 抗浮（不分级别/地基）——
UPLIFT = {"基本": 1.10, "特殊": 1.05}
# —— 7.4 节 基底应力不均匀系数（上限）——
BEARING = {"松软": {"基本": 1.5, "特殊": 2.0},
           "中等坚实": {"基本": 2.0, "特殊": 2.5},
           "坚实": {"基本": 2.5, "特殊": 3.0}}
# —— 8.3.11 镇墩 ——
PIER = {"抗滑": {"基本": 1.30, "特殊": 1.10}, "抗倾": {"基本": 1.50, "特殊": 1.20}}


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _norm_level(s):
    s = str(s).strip().replace("、", ",").replace("，", ",")
    if s in ("4", "5", "4,5"):
        return "4,5"
    try:
        i = int(s)
        return i if i in (1, 2, 3) else None
    except Exception:
        return None


def _norm_combo(s):
    s = (s or "").strip()
    for k in ("特殊II", "特殊I", "特殊", "基本"):
        if s.startswith(k):
            return k
    return s


def _ge(name, val, lim, bad, note=""):
    ok = val >= lim - 1e-9
    print("  %-30s : %s  %s  %s   %s%s" % (name, _f(val, 3), "≥" if ok else "★<", _f(lim, 2),
                                           "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s = %s < 允许值 %s" % (name, _f(val, 3), _f(lim, 2)))
    return ok


def _le(name, val, lim, bad, note=""):
    ok = val <= lim + 1e-9
    print("  %-30s : %s  %s  %s   %s%s" % (name, _f(val, 3), "≤" if ok else "★>", _f(lim, 2),
                                           "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s = %s > 允许值 %s" % (name, _f(val, 3), _f(lim, 2)))
    return ok


def _get_k(a):
    """优先 --k；否则由 抗滑力/滑动力（或 ∑G/∑U）计算。"""
    if a.k is not None:
        return a.k, "报告/给定 K"
    if a.resisting is not None and a.driving is not None and a.driving > 0:
        return a.resisting / a.driving, "K = 抗滑力/滑动力 = %s/%s" % (_f(a.resisting), _f(a.driving))
    return None, None


def mode_slide(a, bad, warn):
    fnd = (a.foundation or "土基").strip()
    combo = _norm_combo(a.combo)
    formula = (a.formula or "抗剪").strip()
    key = "岩基抗剪断" if (fnd == "岩基" and formula in ("抗剪断", "剪断")) else fnd
    if key not in SLIDE:
        print("  ★ --foundation 应为 土基 / 岩基", file=sys.stderr)
        return 2
    if combo not in ("基本", "特殊I", "特殊II"):
        print("  ★ --combo 应为 基本 / 特殊I / 特殊II", file=sys.stderr)
        return 2
    tbl = SLIDE[key][combo]
    k, how = _get_k(a)
    print("依据               : GB 50265 7.3.5 ★ 表 7.3.5（%s / %s）" % (key, combo))
    if isinstance(tbl, dict):
        lv = _norm_level(a.level)
        if lv is None:
            print("  ★ %s 需给 --level（1/2/3/4,5）" % key, file=sys.stderr)
            return 2
        lim = tbl[lv]
        print("  地基类别 / 组合 / 级别 : %s / %s / %s" % (fnd, combo, lv))
    else:
        lim = tbl
        print("  地基类别 / 组合 / 公式 : %s / %s / 抗剪断（不分级别）" % (fnd, combo))
    print("-" * 62)
    if k is None:
        print("  ▲ 未给 --k 也未能由 --resisting/--driving 算出 → 仅列允许值 %s" % _f(lim, 2))
        warn.append("未提供 K 值，无法判定；请给 --k 或 --resisting/--driving")
        return 0
    print("  %s" % how)
    _ge("抗滑稳定安全系数 K", k, lim, bad)
    if combo == "特殊II" and a.with_check_level:
        print("  ★ 警告：地震荷载不应与校核运用水位组合（7.3.3）——已声明与校核水位组合，属组合错误")


def mode_uplift(a, bad, warn):
    combo = "基本" if (a.combo or "基本").startswith("基本") else "特殊"
    lim = UPLIFT[combo]
    k, how = _get_k(a)
    print("依据               : GB 50265 7.3.7 / 7.3.8 ★（抗浮，**不分级别与地基类别**）")
    print("  荷载组合           : %s" % combo)
    print("-" * 62)
    if k is None:
        print("  ▲ 未给 --k 也未能由 --resisting/--driving 算出 → 仅列允许值 %s" % _f(lim, 2))
        warn.append("未提供 K 值，无法判定；K = ∑G（基底面以上全部重力）/∑U（基底面扬压力）")
        return 0
    print("  %s" % how)
    _ge("抗浮稳定安全系数 K", k, lim, bad, "（不分级别/地基 → 一律 %s）" % _f(lim, 2))
    if a.level is not None:
        warn.append("抗浮**不按级别分档**（7.3.8）—— 报告若按级别取值即错")


def mode_bearing(a, bad, warn):
    soil = (a.soil or "").strip()
    if soil not in BEARING:
        print("  ★ --soil 应为 松软 / 中等坚实 / 坚实", file=sys.stderr)
        return 2
    combo = "基本" if (a.combo or "基本").startswith("基本") else "特殊"
    lim = BEARING[soil][combo]
    print("依据               : GB 50265 7.4 节（基底应力不均匀系数，**上限型**）")
    print("  地基土质 / 组合    : %s / %s" % (soil, combo))
    ratio = None
    if a.sigma_max is not None and a.sigma_min is not None:
        if a.sigma_min <= 0:
            print("  ★ σmin = %s ≤ 0 —— 基底出现拉应力（岩基上防洪墙不应出现，见 GB 50286 9.2.10）" % _f(a.sigma_min))
            bad.append("基底出现拉应力（σmin %s ≤ 0）" % _f(a.sigma_min))
            return 1
        ratio = a.sigma_max / a.sigma_min
        print("  σmax / σmin        : %s / %s kPa" % (_f(a.sigma_max), _f(a.sigma_min)))
    elif a.ratio is not None:
        ratio = a.ratio
    else:
        print("  ▲ 未给 --sigma-max/--sigma-min 或 --ratio → 仅列允许值 %s" % _f(lim, 2))
        warn.append("未提供 σmax/σmin，无法判定")
        return 0
    print("-" * 62)
    _le("基底应力不均匀系数 σmax/σmin", ratio, lim, bad, "（越小越有利）")
    if a.allow_bearing is not None and a.sigma_max is not None:
        _le("σmax vs 允许承载力", a.sigma_max, a.allow_bearing, bad)


def mode_pier(a, bad, warn):
    typ = (a.type or "抗滑").strip()
    if typ not in PIER:
        print("  ★ --type 应为 抗滑 / 抗倾", file=sys.stderr)
        return 2
    combo = "基本" if (a.combo or "基本").startswith("基本") else "特殊"
    lim = PIER[typ][combo]
    k, how = _get_k(a)
    print("依据               : GB 50265 8.3.11 镇墩%s稳定" % typ)
    print("  荷载组合           : %s" % combo)
    print("-" * 62)
    if k is None:
        print("  ▲ 未给出 K → 仅列允许值 %s" % _f(lim, 2))
        warn.append("未提供 K 值")
        return 0
    print("  %s" % how)
    _ge("镇墩%s稳定安全系数 K" % typ, k, lim, bad)


def main():
    ap = argparse.ArgumentParser(description="泵房稳定复核")
    ap.add_argument("--mode", required=True, choices=["slide", "uplift", "bearing", "pier"])
    ap.add_argument("--foundation", help="地基类别：土基 / 岩基")
    ap.add_argument("--combo", help="荷载组合：基本 / 特殊I / 特殊II（uplift/bearing/pier 用 基本/特殊）")
    ap.add_argument("--level", default=None, help="泵站建筑物级别 1/2/3/4/5")
    ap.add_argument("--formula", default=None, help="抗剪 / 抗剪断（岩基抗剪断不分级别）")
    ap.add_argument("--soil", help="地基土质：松软 / 中等坚实 / 坚实")
    ap.add_argument("--type", default=None, help="镇墩类型：抗滑 / 抗倾")
    ap.add_argument("--k", type=float, default=None, help="安全系数 K（直接给）")
    ap.add_argument("--resisting", type=float, default=None, help="抗滑力/抗倾力矩/∑G")
    ap.add_argument("--driving", type=float, default=None, help="滑动力/倾覆力矩/∑U")
    ap.add_argument("--sigma-max", type=float, dest="sigma_max", help="最大基底应力 σmax (kPa)")
    ap.add_argument("--sigma-min", type=float, dest="sigma_min", help="最小基底应力 σmin (kPa)")
    ap.add_argument("--ratio", type=float, default=None, help="[可选] 直接给 σmax/σmin")
    ap.add_argument("--allow-bearing", type=float, dest="allow_bearing", help="[可选] 地基允许承载力 (kPa)")
    ap.add_argument("--with-check-level", action="store_true", dest="with_check_level",
                    help="[警告用] 该地震组合是否与校核运用水位组合")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的 K，用于比对")
    args = ap.parse_args()

    bad, warn = [], []
    print("=" * 62)
    if args.mode == "slide":
        rc = mode_slide(args, bad, warn)
    elif args.mode == "uplift":
        rc = mode_uplift(args, bad, warn)
    elif args.mode == "bearing":
        rc = mode_bearing(args, bad, warn)
    else:
        rc = mode_pier(args, bad, warn)
    if rc == 2:
        return 2

    if args.report is not None and args.k is not None:
        print("  %-30s : 报告 %s / 复核 %s" % ("与报告 K 比对", _f(args.report, 3), _f(args.k, 3)))
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
