#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泵站各高程控制点复核（泵站工程报告审查用）。

【它解决什么】
    泵站有一批**由水位控制的高程**：泵房挡水部位顶部高程、水泵安装高程（淹没深度）、
    流道进出口上缘淹没、出水管出口淹没、进水池水下容积。报告常"只算设计运用、漏校核运用"、
    "拿设计水位核安装高程"、"淹没深度取值串位"。本工具按 GB 50265 逐项独立复算并与报告值比对。

【依据】
    GB 50265-2022：
      7.1.3 ★ 泵房挡水部位顶部高程 ≥ 设计/校核运用情况挡水位 + 波浪壅浪 + 安全加高（**取大值**）；表 7.1.3
      7.1.4   位于防洪、挡潮堤坝上的泵房，挡水部位顶高程不应低于相应堤坝顶部高程
      7.1.26  泵房地面层室内地坪应高于室外地坪 0.2 m
      10.1.7-2 立式轴流泵/混流泵基准面最小淹没深度 > 0.5 m（且满足允许吸上真空高度/必需汽蚀余量）
      10.2.2-5 进水流道进口上缘淹没在**进水池最低运行水位**以下 ≥ 0.5 m
      10.2.5-4 出水流道出口上缘淹没在**出水池最低运行水位**以下 0.3~0.5 m
      8.3.3   出水管（淹没出流）出口上缘**宜**淹没在**出水池最低运行水位**以下不小于0.3 m（提示型，不计★）
      8.2.7   进水池水下容积**可**按设计流量下**秒换水系数 30~50** 确定（提示型，不计★）

【用法】
    # 挡水部位顶部高程（设计/校核两运用取大值）
    python calc_pump_elevation.py --mode crest --level 3 \
        --zeta-design 5.20 --zeta-check 5.80 --wave 0.35 --crest-elev 6.60 --dike-crest 6.45
    # 水泵安装高程 → 基准面淹没深度（立式）
    python calc_pump_elevation.py --mode install --install-elev 1.60 --z-in-min 2.20 --vertical
    # 流道/管道淹没（进口/出口/出水管）
    python calc_pump_elevation.py --mode flowpath --part 进口 --struct-elev 1.70 --z-low 2.20
    # 进水池水下容积
    python calc_pump_elevation.py --mode volume --q 10 --volume 420

【退出码】统一语义（家族约定，勿改）
    0 = 满足 · 1 = 不满足 · 2 = 输入错 · 3 = 仅参考值
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— GB 50265 表 7.1.3 泵房挡水部位顶部安全加高 (m)：(设计运用, 校核运用) ——
SA = {
    "1": (0.7, 0.5),
    "2": (0.5, 0.4),
    "3": (0.4, 0.3),
    "4,5": (0.3, 0.2),
}
# —— 流道/管道淹没限值 (m)：下限型；出口另有上限 ——
SUBMERGE = {
    "进口": {"min": 0.5, "max": None, "hard": True,
             "ref": "GB 50265 10.2.2-5（进水池最低运行水位以下**至少**0.5m）"},
    "出口": {"min": 0.3, "max": 0.5, "hard": True,
             "ref": "GB 50265 10.2.5-4（出水池最低运行水位以下**应**淹没 0.3m~0.5m）"},
    "出水管": {"min": 0.3, "max": None, "hard": False,
               "ref": "GB 50265 8.3.3（出水池最低运行水位以下**宜**不小于0.3m）"},
}
COEF_MIN, COEF_MAX = 30.0, 50.0      # 秒换水系数 30~50（GB 50265 8.2.7）


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _norm_level(s):
    s = str(s).strip().replace("、", ",").replace("，", ",")
    if s in ("4", "5", "4,5"):
        return "4,5"
    if s in SA:
        return s
    return None


def _ge(name, val, lim, bad, note=""):
    ok = val >= lim - 1e-9
    print("  %-34s : %s  %s  %s   %s%s" % (name, _f(val), "≥" if ok else "★<", _f(lim),
                                           "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s = %s < %s" % (name, _f(val), _f(lim)))
    return ok


def _le(name, val, lim, bad, note=""):
    ok = val <= lim + 1e-9
    print("  %-34s : %s  %s  %s   %s%s" % (name, _f(val), "≤" if ok else "★>", _f(lim),
                                           "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s = %s > %s" % (name, _f(val), _f(lim)))
    return ok


def _gt(name, val, lim, bad, note=""):
    """严格大于。用于标准措辞为「应大于」的下限（等于也不满足，如 10.1.7-2 的 >0.5m）。"""
    ok = val > lim + 1e-9
    print("  %-34s : %s  %s  %s   %s%s" % (name, _f(val), ">" if ok else "★≤", _f(lim),
                                           "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s = %s ≤ %s（标准为「应大于」）" % (name, _f(val), _f(lim)))
    return ok


def _soft_ge(name, val, lim, warn, note=""):
    """下限型但标准措辞为「宜/可」—— 不满足只出 ▲ 提示，不计入 bad（家族判据方向纪律）。"""
    ok = val >= lim - 1e-9
    print("  %-34s : %s  %s  %s   %s%s" % (name, _f(val), "≥" if ok else "▲<", _f(lim),
                                           "满足" if ok else "▲ 低于推荐值", ("  " + note) if note else ""))
    if not ok:
        warn.append("%s = %s < %s（标准措辞为「宜/可」，属推荐值）" % (name, _f(val), _f(lim)))
    return ok


def mode_crest(a, bad, warn):
    lv = _norm_level(a.level)
    if lv is None:
        print("  ★ --level 应为 1/2/3/4/5（4、5 级可写 4,5）", file=sys.stderr)
        return 2
    if a.zeta_design is None or a.crest_elev is None:
        print("  ★ crest 需要 --zeta-design 与 --crest-elev（校核运用强烈建议给 --zeta-check）",
              file=sys.stderr)
        return 2
    sa_des, sa_chk = SA[lv]
    wave = a.wave if a.wave is not None else 0.0
    if a.wave is None:
        warn.append("未给 --wave（波浪壅浪计算高度按 0 计）—— 实际须由报告提供波浪爬高与壅浪高度")
    print("依据               : GB 50265-2022 7.1.3 ★ + 表 7.1.3；7.1.4")
    print("建筑物级别 / 安全加高 : %s 级  设计 %s m / 校核 %s m" % (lv, _f(sa_des), _f(sa_chk)))
    print("-" * 62)
    need_des = a.zeta_design + wave + sa_des
    _f_ = lambda v: _f(v)
    print("  设计运用：挡水位 %s + 波浪壅浪 %s + 安全加高 %s = 需求顶高程 %s" % (
        _f_(a.zeta_design), _f_(wave), _f_(sa_des), _f_(need_des)))
    needs = [need_des]
    if a.zeta_check is not None:
        need_chk = a.zeta_check + wave + sa_chk
        print("  校核运用：挡水位 %s + 波浪壅浪 %s + 安全加高 %s = 需求顶高程 %s" % (
            _f_(a.zeta_check), _f_(wave), _f_(sa_chk), _f_(need_chk)))
        needs.append(need_chk)
    else:
        warn.append("未给 --zeta-check（校核运用）—— 强条要求**两种运用取大值**，漏校核是最常见错情")
    req = max(needs)
    print("-" * 62)
    print("  取大值需求顶高程  : %s m%s" % (_f(req), "（设计运用）" if req == need_des else "（校核运用）"))
    _ge("泵房挡水部位顶部高程", a.crest_elev, req, bad, "（取大值）")
    if a.dike_crest is not None:
        _ge("  堤坝上泵房 ≥ 堤坝顶部高程", a.crest_elev, a.dike_crest, bad, "GB 50265 7.1.4")
    if a.indoor_elev is not None and a.outdoor_elev is not None:
        _ge("室内地坪 ≥ 室外地坪 + 0.2", a.indoor_elev, a.outdoor_elev + 0.2, bad, "GB 50265 7.1.26")
    if a.report is not None:
        d = abs(a.crest_elev - a.report)
        print("  %-34s : 报告 %s / 采用 %s  |Δ|=%.3f" % ("报告顶部高程比对", _f(a.report), _f(a.crest_elev), d))


def mode_install(a, bad, warn):
    if a.install_elev is None or a.z_in_min is None:
        print("  ★ install 需要 --install-elev 与 --z-in-min（进水池最低运行水位）", file=sys.stderr)
        return 2
    print("依据               : GB 50265-2022 10.1.7（安装高程 / 淹没深度 / 汽蚀）")
    sub = a.z_in_min - a.install_elev
    print("  进水池最低运行水位 : %s m" % _f(a.z_in_min))
    print("  水泵安装高程(基准面): %s m" % _f(a.install_elev))
    print("  → 基准面淹没深度    : %s m" % _f(sub))
    print("-" * 62)
    if a.vertical:
        _gt("立式轴流/混流泵基准面淹没深度", sub, 0.5, bad, "应大于0.5 m（10.1.7-2）")
    else:
        warn.append("未声明 --vertical（立式轴流/混流泵才有 >0.5 m 的淹没深度硬要求）；"
                    "卧式泵须核允许吸上真空高度/必需汽蚀余量")
    if a.npsha is not None and a.npshr is not None:
        _ge("装置汽蚀余量 NPSHa ≥ 必需 NPSHr", a.npsha, a.npshr, bad, "10.1.7-1")
    else:
        warn.append("未给 --npsha/--npshr —— 10.1.7-1 要求在**最低运行水位**满足允许吸上真空高度或必需汽蚀余量，"
                    "报告须提供该参数（含沙水源/变转速须修正）")
    if a.report is not None:
        print("  %-34s : 报告安装高程 %s（复算按 %s）" % ("报告值比对", _f(a.report), _f(a.install_elev)))


def mode_flowpath(a, bad, warn):
    part = a.part
    if part not in SUBMERGE:
        print("  ★ --part 应为 进口 / 出口 / 出水管", file=sys.stderr)
        return 2
    if a.struct_elev is None or a.z_low is None:
        print("  ★ flowpath 需要 --struct-elev（结构上缘高程）与 --z-low（对应最低运行水位）", file=sys.stderr)
        return 2
    info = SUBMERGE[part]
    sub = a.z_low - a.struct_elev
    print("依据               : %s" % info["ref"])
    print("  最低运行水位       : %s m" % _f(a.z_low))
    print("  %s上缘高程         : %s m" % (part, _f(a.struct_elev)))
    print("  → 上缘淹没深度      : %s m" % _f(sub))
    print("-" * 62)
    if info["hard"]:
        _ge("%s上缘淹没深度" % part, sub, info["min"], bad)
    else:
        _soft_ge("%s上缘淹没深度" % part, sub, info["min"], warn)
    if info["max"] is not None:
        _le("  %s上缘淹没深度上限" % part, sub, info["max"], bad, "过大则增加水力损失")


def mode_volume(a, bad, warn):
    if a.q is None or a.volume is None:
        print("  ★ volume 需要 --q（设计流量 m³/s）与 --volume（报告进水池水下容积 m³）", file=sys.stderr)
        return 2
    v_min = COEF_MIN * a.q
    v_max = COEF_MAX * a.q
    coef = a.volume / a.q if a.q else float("inf")
    print("依据               : GB 50265-2022 8.2.7（秒换水系数 30~50，措辞为「可按」）")
    print("  设计流量 Q         : %s m³/s" % _f(a.q))
    print("  报告水下容积 V     : %s m³" % _f(a.volume, 0))
    print("  → 秒换水系数 V/Q   : %s s（宜 30~50）" % _f(coef, 1))
    print("  → 对应容积区间     : %s ~ %s m³" % (_f(v_min, 0), _f(v_max, 0)))
    print("-" * 62)
    _soft_ge("进水池水下容积 V", a.volume, v_min, warn, "（推荐下限 = 30·Q）")
    if a.volume > v_max + 1e-6:
        warn.append("V/Q = %s s > 50 —— 容积偏大，可能不经济（宜在 30~50 之间）" % _f(coef, 1))


def main():
    ap = argparse.ArgumentParser(description="泵站高程控制点复核")
    ap.add_argument("--mode", required=True, choices=["crest", "install", "flowpath", "volume"])
    # crest
    ap.add_argument("--level", default=None, help="泵站建筑物级别 1/2/3/4/5（4、5 可写 4,5）")
    ap.add_argument("--zeta-design", type=float, dest="zeta_design", help="设计运用挡水位 (m)")
    ap.add_argument("--zeta-check", type=float, dest="zeta_check", help="校核运用挡水位 (m)")
    ap.add_argument("--wave", type=float, default=None, help="波浪+壅浪计算高度 (m)")
    ap.add_argument("--crest-elev", type=float, dest="crest_elev", help="泵房挡水部位顶部高程 (m)")
    ap.add_argument("--dike-crest", type=float, dest="dike_crest", help="[可选] 所在堤坝顶部高程 (m)")
    ap.add_argument("--indoor-elev", type=float, dest="indoor_elev", help="[可选] 室内地坪高程 (m)")
    ap.add_argument("--outdoor-elev", type=float, dest="outdoor_elev", help="[可选] 室外地坪高程 (m)")
    # install
    ap.add_argument("--install-elev", type=float, dest="install_elev", help="水泵安装高程(基准面) (m)")
    ap.add_argument("--z-in-min", type=float, dest="z_in_min", help="进水池最低运行水位 (m)")
    ap.add_argument("--vertical", action="store_true", help="立式轴流泵/混流泵（淹没深度 >0.5 m 硬要求）")
    ap.add_argument("--npsha", type=float, help="[可选] 装置汽蚀余量 (m)")
    ap.add_argument("--npshr", type=float, help="[可选] 必需汽蚀余量 (m)")
    # flowpath
    ap.add_argument("--part", help="进口 / 出口 / 出水管")
    ap.add_argument("--struct-elev", type=float, dest="struct_elev", help="结构上缘高程 (m)")
    ap.add_argument("--z-low", type=float, dest="z_low", help="对应最低运行水位 (m)")
    # volume
    ap.add_argument("--q", type=float, help="设计流量 (m³/s)")
    ap.add_argument("--volume", type=float, help="进水池水下容积 (m³)")
    # 报告值
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的结论值，用于比对")
    args = ap.parse_args()

    bad, warn = [], []
    print("=" * 62)
    if args.mode == "crest":
        rc = mode_crest(args, bad, warn)
    elif args.mode == "install":
        rc = mode_install(args, bad, warn)
    elif args.mode == "flowpath":
        rc = mode_flowpath(args, bad, warn)
    else:
        rc = mode_volume(args, bad, warn)
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
