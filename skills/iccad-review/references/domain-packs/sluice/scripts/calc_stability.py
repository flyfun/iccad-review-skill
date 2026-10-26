#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水闸稳定复算工具 —— 抗滑 / 抗浮 / 基底应力。

【它解决什么问题】
    审查报告时经常遇到"抗滑 K=1.28，满足""抗浮 K=1.12，满足"这类结论。
    光看数字判不了真假——必须自己把式子和限值都过一遍。
    本脚本把这三类稳定验算做成"输入参数 → 算 → 按规范限值判"的计算器。

【限值从哪来】
    全部取自 SL 265-2016《水闸设计规范》**原文表格**（已逐张核对提取）：
      表 7.3.13  土基上沿闸室基底面抗滑稳定安全系数的允许值
      表 7.3.14  岩基上沿闸室基底面抗滑稳定安全系数的允许值
      表 7.3.5   土基上闸室基底应力最大值与最小值之比的允许值
      表 7.3.10  摩擦系数 f 值
      表 7.3.11  综合摩擦系数折算用的 φ0、C0 值
      第 7.3.16 条（正文）  抗浮稳定安全系数 1.10 / 1.05

【⚠️ 公式本体的重要提示】
    SL 265 原文里公式是**嵌入图形对象**（OMML/图片），机器提取不到。
    本脚本的公式按**条文符号定义 + 水力学通用形式**还原：
      7.3.6-1 抗剪：      K  = f·ΣG / ΣH
      7.3.6-2 抗剪断：    K  = (f'·ΣG + C'·A) / ΣH
      7.3.16  抗浮：      Kf = ΣV / ΣU
      7.3.4   基底应力：  Pmax,min = ΣG/A ± M/W
    这些形式与条文符号一致，但**使用前请与规范原文核对**（尤其是符号约定与
    扬压力的正负号处理）。

用法示例：
    # 抗滑（土基、3 级、基本组合、抗剪公式）
    python calc_stability.py --mode sliding --level 3 --combo basic \
        --foundation soil --sum-g 42000 --sum-h 15000 --f 0.35

    # 抗滑（黏性土、抗剪断/综合公式：给 φ 与 C0 自动折算）
    python calc_stability.py --mode sliding --level 2 --foundation soil \
        --sum-g 42000 --sum-h 15000 --phi 18 --c0 25 --area 300

    # 抗浮（检修抽空工况）
    python calc_stability.py --mode float --sum-v 38000 --sum-u 33000

    # 基底应力（含地基允许承载力判定）
    python calc_stability.py --mode bearing --sum-g 42000 --area 300 \
        --moment 9000 --allow-bearing 250 --soil-type medium
"""
import argparse
import math

# ---------------------------------------------------------------------------
# 规范限值表（均取自 SL 265-2016 原文表格，2026-10-11 实测提取）
# ---------------------------------------------------------------------------

# 表 7.3.13 土基抗滑稳定安全系数允许值
#   行 = 荷载组合；列 = 水闸级别 [1级, 2级, 3级, 4、5级]
#   注：特殊组合I 适用施工/检修/校核洪水位；特殊组合II 适用地震
ALLOW_SOIL_SLIDING = {
    "basic":    [1.35, 1.30, 1.25, 1.20],
    "special1": [1.20, 1.15, 1.10, 1.05],
    "special2": [1.10, 1.05, 1.05, 1.00],
}

# 表 7.3.14 岩基抗滑稳定安全系数允许值
#   按公式(7.3.6-1)——即抗剪 f 公式时：[1级, 2、3级, 4、5级]
ALLOW_ROCK_SHEAR = {
    "basic":    [1.10, 1.08, 1.05],
    "special1": [1.05, 1.03, 1.00],
    "special2": [1.00, 1.00, 1.00],
}
#   按公式(7.3.8)——即抗剪断公式时（不分级别）
ALLOW_ROCK_SHEARFRICTION = {"basic": 3.00, "special1": 2.50, "special2": 2.30}

# 表 7.3.5 土基基底应力最大值/最小值之比的允许值
#   行 = 地基土质；值 = [基本组合, 特殊组合]
ALLOW_STRESS_RATIO = {
    "soft":   [1.50, 2.00],   # 松软
    "medium": [2.00, 2.50],   # 中等坚实
    "hard":   [2.50, 3.00],   # 坚实
}

# 第 7.3.16 条（正文明文）：抗浮稳定安全系数，与级别、地基均无关
ALLOW_FLOAT = {"basic": 1.10, "special1": 1.05, "special2": 1.05}

# 表 7.3.10 基底面与地基之间的摩擦系数 f 值（区间，供参考/校验报告取值）
F_TABLE = {
    "黏土-软弱": (0.20, 0.25), "黏土-中等坚硬": (0.25, 0.35), "黏土-坚硬": (0.35, 0.45),
    "壤土、粉质壤土": (0.25, 0.40), "砂壤土、粉砂土": (0.35, 0.40),
    "细砂、极细砂": (0.40, 0.45), "中砂、粗砂": (0.45, 0.50),
    "砂砾石": (0.40, 0.50), "砾石、卵石": (0.50, 0.55), "碎石土": (0.40, 0.50),
    "软质岩石-极软": (0.40, 0.45),
}

# 表 7.3.11 φ0、C0 取值规则（土质地基）：φ0 为折减后内摩擦角，C0 为折减后黏结力
PHI0_RATIO = {"cohesive": 0.90, "granular": 0.875}   # 黏性土 0.9φ；砂性土 (0.85~0.9)φ 取中
C0_RATIO = {"cohesive": 0.25, "granular": 0.0}        # 黏性土 (0.2~0.3)C 取中；砂性土 0

LEVEL_IDX = {1: 0, 2: 1, 3: 2, 4: 3, 5: 3}            # 水闸级别 → 表列索引（4、5 级同列）
COMBO_CN = {"basic": "基本组合", "special1": "特殊组合I", "special2": "特殊组合II"}


def allow_level_index(level):
    """把水闸级别（1~5）映射到限值表的列索引；非法级别报错。"""
    if level not in LEVEL_IDX:
        raise ValueError("水闸级别须为 1~5，收到 %r" % level)
    return LEVEL_IDX[level]


def verdict(value, allow):
    """统一的判定输出：计算值 vs 允许值（越大越安全）。"""
    ok = value >= allow
    return ok, ("满足" if ok else "不满足"), "≥" if ok else "<"


# ---------------------------------------------------------------------------
# 三类复算
# ---------------------------------------------------------------------------

def calc_sliding(a):
    """抗滑稳定安全系数。

    抗剪公式（7.3.6-1，砂性土 / 一般情况）：
        K = f·ΣG / ΣH
    抗剪断公式（7.3.6-2 土基黏性土大型水闸 / 7.3.8 岩基）：
        K = (f'·ΣG + C'·A) / ΣH
    其中 ΣG 为全部竖向力（**含扬压力**，即有效重量），ΣH 为水平滑动力。
    """
    if a.sum_h <= 0:
        raise ValueError("ΣH 必须为正（水平滑动力）")
    sum_g = a.sum_g

    print("【抗滑稳定】SL 265 第 7.3.6 条 / 7.3.8 条")
    print("  ΣG(竖向力合力，含扬压力) = %.0f kN" % sum_g)
    print("  ΣH(水平滑动力)          = %.0f kN" % a.sum_h)

    if a.phi is not None:
        # 抗剪断 / 综合摩擦：给 φ、C0、A → 按表 7.3.11 规则折减后算
        if a.c0 is None or a.area is None:
            raise ValueError("使用 --phi 时须同时给 --c0 与 --area")
        frac = "cohesive" if a.soil_class == "cohesive" else "granular"
        phi0 = a.phi * PHI0_RATIO[frac]          # 表 7.3.11 折减
        c0 = a.c0 * C0_RATIO[frac]
        tan_phi0 = math.tan(math.radians(phi0))
        numer = tan_phi0 * sum_g + c0 * a.area
        k = numer / a.sum_h
        print("  φ=%.1f° → φ0=%.2f°(表7.3.11折减)  C0=%.2f kPa  A=%.1f m²"
              % (a.phi, phi0, c0, a.area))
        print("  公式(7.3.6-2 / 7.3.8)：K = (tanφ0·ΣG + C0·A) / ΣH")
        print("                        = (%.4f×%.0f + %.2f×%.1f) / %.0f"
              % (tan_phi0, sum_g, c0, a.area, a.sum_h))
    else:
        # 抗剪公式：给 f
        if a.f is None:
            raise ValueError("须给出 --f（抗剪公式）或 --phi/--c0/--area（抗剪断公式）")
        k = a.f * sum_g / a.sum_h
        print("  f(摩擦系数) = %.3f" % a.f)
        print("  公式(7.3.6-1)：K = f·ΣG / ΣH = %.3f×%.0f / %.0f"
              % (a.f, sum_g, a.sum_h))

    # 取容许值
    if a.foundation == "rock":
        if a.phi is not None:
            allow = ALLOW_ROCK_SHEARFRICTION[a.combo]
            src = "表7.3.14（按公式7.3.8抗剪断计算，不分级别）"
        else:
            allow = ALLOW_ROCK_SHEAR[a.combo][allow_level_index(a.level)]
            src = "表7.3.14（按公式7.3.6-1计算，%d级）" % a.level
    else:
        allow = ALLOW_SOIL_SLIDING[a.combo][allow_level_index(a.level)]
        src = "表7.3.13（土基，%d级）" % a.level

    ok, v, op = verdict(k, allow)
    print("  ── 计算值 K = %.3f" % k)
    print("  ── 允许值 [K] = %.2f   （%s，%s）" % (allow, src, COMBO_CN[a.combo]))
    print("  ==>> %s：K=%.3f %s [K]=%.2f" % (v, k, op, allow))
    return 0 if ok else 1


def calc_float(a):
    """抗浮稳定安全系数（SL 265 第 7.3.16 条）。

        Kf = ΣV / ΣU
    ΣV = 作用在闸室上全部向下的铅直力之和；ΣU = 基底面上的扬压力。
    基本组合 ≥1.10、特殊组合 ≥1.05，**与级别和地基条件无关**。
    提示：检修抽空工况常为控制工况，别漏。
    """
    if a.sum_u <= 0:
        raise ValueError("ΣU 必须为正（扬压力）")
    kf = a.sum_v / a.sum_u
    allow = ALLOW_FLOAT[a.combo]
    print("【抗浮稳定】SL 265 第 7.3.16 条")
    print("  ΣV(向下铅直力) = %.0f kN" % a.sum_v)
    print("  ΣU(扬压力)     = %.0f kN" % a.sum_u)
    print("  公式(7.3.16)：Kf = ΣV / ΣU = %.3f" % kf)
    ok, v, op = verdict(kf, allow)
    print("  ── 允许值 [Kf] = %.2f  （第7.3.16条正文，%s，与级别/地基无关）"
          % (allow, COMBO_CN[a.combo]))
    print("  ==>> %s：Kf=%.3f %s [Kf]=%.2f" % (v, kf, op, allow))
    return 0 if ok else 1


def calc_bearing(a):
    """基底应力与不均匀系数（SL 265 第 7.3.4 / 7.3.2 条 + 表 7.3.5）。

        Pmax,min = ΣG/A ± M/W ，矩形底板 W = B·L²/6（沿力矩方向）
    这里采用等价形式：Pmax,min = ΣG/A ± 6M/(B·L²)。
    为简化，用户直接给 A（面积）与 W（截面模量，可由 --area 与 --length 推）。
    判定：① Pmax ≤ 1.2×地基允许承载力；② η = Pmax/Pmin ≤ 表7.3.5 允许值。
    """
    if a.area <= 0:
        raise ValueError("--area 必须为正")
    if a.section_modulus is None:
        raise ValueError("基底应力需给 --section-modulus W（截面模量，m³）；"
                         "矩形底板 W = B·L²/6")
    p_avg = a.sum_g / a.area
    dp = a.moment / a.section_modulus
    pmax, pmin = p_avg + dp, p_avg - dp
    print("【基底应力】SL 265 第 7.3.4 / 7.3.2 条 + 表 7.3.5")
    print("  ΣG=%.0f kN  A=%.1f m²  M=%.0f kN·m  W=%.2f m³"
          % (a.sum_g, a.area, a.moment, a.section_modulus))
    print("  公式(7.3.4-1)：Pmax,min = ΣG/A ± M/W")
    print("  ── 平均基底应力 P = %.1f kPa" % p_avg)
    print("  ── Pmax = %.1f kPa   Pmin = %.1f kPa" % (pmax, pmin))

    rc = 0
    # ① 承载力判定（7.3.2-1：平均 < [R]，最大 < 1.2[R]）
    if a.allow_bearing:
        print("  ① 承载力（地基允许承载力 [R]=%.0f kPa）" % a.allow_bearing)
        print("     平均 P=%.1f %s [R]=%.0f" % (p_avg, "≤" if p_avg <= a.allow_bearing else ">", a.allow_bearing))
        cap_ok = (p_avg <= a.allow_bearing) and (pmax <= 1.2 * a.allow_bearing)
        print("     最大 Pmax=%.1f %s 1.2[R]=%.0f  → %s"
              % (pmax, "≤" if pmax <= 1.2 * a.allow_bearing else ">",
                 1.2 * a.allow_bearing, "满足" if cap_ok else "不满足"))
        if not cap_ok:
            rc = 1
    # ② 不均匀系数判定（表 7.3.5）
    if pmin <= 0:
        print("  ② 不均匀系数：Pmin=%.1f ≤ 0，基底出现拉应力（非地震情况不允许，见7.3.2）" % pmin)
        rc = 1
    elif a.soil_type:
        col = 0 if a.combo == "basic" else 1
        allow_ratio = ALLOW_STRESS_RATIO[a.soil_type][col]
        eta = pmax / pmin
        # 注意：不均匀系数是"越小越安全"，判定方向与抗滑/抗浮相反
        ok = eta <= allow_ratio
        v, op = ("满足", "≤") if ok else ("不满足", ">")
        print("  ② 不均匀系数 η = Pmax/Pmin = %.1f/%.1f = %.2f" % (pmax, pmin, eta))
        print("     允许值 = %.2f （表7.3.5，%s，%s）"
              % (allow_ratio, {"soft": "松软", "medium": "中等坚实", "hard": "坚实"}[a.soil_type],
                 "基本组合" if col == 0 else "特殊组合"))
        print("     ==>> %s：η=%.2f %s %.2f" % (v, eta, op, allow_ratio))
        if not ok:
            rc = 1
    return rc


def main():
    ap = argparse.ArgumentParser(description="水闸稳定复算（SL 265-2016）")
    ap.add_argument("--mode", required=True, choices=["sliding", "float", "bearing"],
                    help="复算类型：sliding 抗滑 / float 抗浮 / bearing 基底应力")
    ap.add_argument("--level", type=int, default=3, help="水闸级别 1~5（默认 3）")
    ap.add_argument("--combo", default="basic", choices=["basic", "special1", "special2"],
                    help="荷载组合：basic 基本 / special1 特殊I(施工·检修·校核) / special2 特殊II(地震)")
    ap.add_argument("--foundation", default="soil", choices=["soil", "rock"],
                    help="地基类型：soil 土基 / rock 岩基（抗滑用）")
    # 抗滑
    ap.add_argument("--sum-g", type=float, default=None, help="竖向力合力 ΣG，kN（含扬压力）")
    ap.add_argument("--sum-h", type=float, default=None, help="水平滑动力 ΣH，kN")
    ap.add_argument("--f", type=float, default=None, help="摩擦系数 f（抗剪公式 7.3.6-1）")
    ap.add_argument("--phi", type=float, default=None, help="内摩擦角 φ，°（抗剪断公式，自动按表7.3.11折减）")
    ap.add_argument("--c0", type=float, default=None, help="黏结力 C，kPa（抗剪断公式）")
    ap.add_argument("--soil-class", default="cohesive", choices=["cohesive", "granular"],
                    help="土性：cohesive 黏性土 / granular 砂性土（抗剪断折减用）")
    # 抗浮
    ap.add_argument("--sum-v", type=float, default=None, help="向下铅直力之和 ΣV，kN")
    ap.add_argument("--sum-u", type=float, default=None, help="扬压力 ΣU，kN")
    # 基底应力
    ap.add_argument("--area", type=float, default=None, help="基底面积 A，m²")
    ap.add_argument("--moment", type=float, default=0.0, help="对基底形心的力矩 M，kN·m")
    ap.add_argument("--section-modulus", type=float, default=None, help="截面模量 W，m³")
    ap.add_argument("--allow-bearing", type=float, default=None, help="地基允许承载力 [R]，kPa")
    ap.add_argument("--soil-type", default=None, choices=["soft", "medium", "hard"],
                    help="土基软硬：soft 松软 / medium 中等坚实 / hard 坚实（表7.3.5）")
    a = ap.parse_args()

    if a.mode == "sliding":
        rc = calc_sliding(a)
    elif a.mode == "float":
        rc = calc_float(a)
    else:
        rc = calc_bearing(a)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
