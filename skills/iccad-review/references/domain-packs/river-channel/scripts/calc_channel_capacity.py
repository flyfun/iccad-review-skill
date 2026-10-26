#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""河道过流能力复核器 —— 曼宁均匀流（矩形 / 梯形 / 复式断面）。

【复算什么】
    Q = (1/n)·A·R^(2/3)·i^(1/2)      —— 均匀流过流能力（曼宁公式）
      - 正算：给水深 h → 过流能力 Q、流速 v、弗劳德数 Fr
      - 反算：给设计流量 Q → 均匀流水深 h（二分法）
    另算临界水深 hc（判别急/缓流）。

【断面】
    rect      矩形：给底宽 b
    trap      梯形：给底宽 b、边坡 m（H:V，即 1:m）
    compound  复式：主槽梯形(b1,m1,n1) + 滩地(宽 b2, 坡 m2, 糙率 n2)，--bank-h 给主槽岸顶高

【提示】
    糙率 n 用参考值（下方 N_REF，**非规范强制**），实际取值须依报告/专业判断。
    设计洪水位、允许流速等应以报告与规范原文为准。

【用法】
    python calc_channel_capacity.py --shape trap --b 30 --m 2.0 --n 0.030 --i 0.0005 --h 3.0
    python calc_channel_capacity.py --shape trap --b 30 --m 2.0 --n 0.030 --i 0.0005 --q 300
    python calc_channel_capacity.py --shape compound --b1 40 --m1 1.5 --n1 0.028 --b2 50 --m2 4 --n2 0.040 \
        --bank-h 4.0 --i 0.0003 --h 6.0
"""
import argparse
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 参考糙率（仅提示用，非规范强制值）
N_REF = {
    "0.020": "浆砌石/混凝土衬砌",
    "0.025": "平整土渠/干砌石",
    "0.030": "一般土质河道",
    "0.035": "有杂草土渠/砾石河床",
    "0.040": "卵石/乱石河床",
    "0.050": "植被茂密/山区粗糙河床",
}

G = 9.81


def section_geom(shape, h, p):
    """返回 (A, P, T)：过水面积、湿周、水面宽。"""
    if shape == "rect":
        b = p["b"]
        A = b * h
        P = b + 2 * h
        T = b
        return A, P, T
    if shape == "trap":
        b, m = p["b"], p["m"]
        A = (b + m * h) * h
        P = b + 2 * h * math.sqrt(1 + m * m)
        T = b + 2 * m * h
        return A, P, T
    if shape == "compound":
        b1, m1 = p["b1"], p["m1"]
        b2, m2, bh = p["b2"], p["m2"], p["bank_h"]
        # 主槽（水深截到岸顶）
        hm = min(h, bh)
        A1 = (b1 + m1 * hm) * hm
        P1 = b1 + 2 * hm * math.sqrt(1 + m1 * m1)
        T1 = b1 + 2 * m1 * hm
        if h <= bh:
            return A1, P1, T1
        # 滩地（两侧对称）：岸顶以上，平滩宽 b2/2（每侧），再以 m2 向上
        d = h - bh
        A_fp_side = (b2 / 2) * d + 0.5 * m2 * d * d
        P_fp_side = (b2 / 2) + d * math.sqrt(1 + m2 * m2)
        A = A1 + 2 * A_fp_side
        P = P1 + 2 * (d + P_fp_side)          # 含主槽两侧岸壁高 d
        T = T1 + 2 * (b2 / 2 + m2 * d)
        return A, P, T
    raise ValueError(shape)


def discharge(shape, h, p):
    A, P, T = section_geom(shape, h, p)
    if A <= 0 or P <= 0:
        return 0.0, 0.0, 0.0, 0.0
    R = A / P
    Q = (1.0 / p["n"]) * A * R ** (2 / 3) * math.sqrt(p["i"])
    v = Q / A
    Fr = v / math.sqrt(G * (A / T)) if T > 0 else 0.0
    return Q, v, Fr, R


def solve_h(shape, p, q):
    """二分法反求均匀流水深。"""
    lo, hi = 1e-4, 1.0
    for _ in range(200):
        if discharge(shape, hi, p)[0] >= q:
            break
        hi *= 1.6
        if hi > 1e5:
            return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if discharge(shape, mid, p)[0] < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def critical_depth(shape, p, q):
    """临界水深：解 Q²·T/(g·A³)=1。"""
    lo, hi = 1e-4, 1.0
    for _ in range(300):
        A, _, T = section_geom(shape, hi, p)
        if A > 0 and q * q * T / (G * A ** 3) <= 1:
            break
        hi *= 1.5
        if hi > 1e5:
            return None
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        A, _, T = section_geom(shape, mid, p)
        f = q * q * T / (G * A ** 3) - 1.0
        if f > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def main():
    ap = argparse.ArgumentParser(description="河道过流能力复核（曼宁均匀流）")
    ap.add_argument("--shape", choices=["rect", "trap", "compound"], required=True)
    ap.add_argument("--b", type=float, help="矩形/梯形 底宽（m）")
    ap.add_argument("--m", type=float, help="梯形 边坡 m（H:V）")
    ap.add_argument("--b1", type=float, help="复式 主槽底宽（m）")
    ap.add_argument("--m1", type=float, help="复式 主槽边坡")
    ap.add_argument("--b2", type=float, help="复式 每侧滩地宽（m）")
    ap.add_argument("--m2", type=float, default=0.0, help="复式 滩地以上边坡")
    ap.add_argument("--bank-h", type=float, help="复式 主槽岸顶高（m）")
    ap.add_argument("--n", type=float, help="糙率 n（矩形/梯形）")
    ap.add_argument("--n1", type=float, help="复式 主槽糙率")
    ap.add_argument("--n2", type=float, default=None, help="复式 滩地糙率")
    ap.add_argument("--i", type=float, required=True, help="底坡 i（如 0.0005）")
    ap.add_argument("--h", type=float, default=None, help="水深 h（正算）")
    ap.add_argument("--q", type=float, default=None, help="设计流量 Q（反算水深）")
    ap.add_argument("--v-allow", type=float, default=None, help="允许流速（m/s），用于提示")
    args = ap.parse_args()

    # 组装断面参数
    if args.shape == "compound":
        for k in ("b1", "m1", "b2", "bank_h", "n1"):
            if getattr(args, k) is None:
                ap.error("复式断面需 --%s" % k.replace("_", "-"))
        p = {"b1": args.b1, "m1": args.m1, "b2": args.b2, "m2": args.m2,
             "bank_h": args.bank_h, "n": args.n1, "n2": args.n2 or args.n1}
    else:
        if args.b is None or args.n is None:
            ap.error("矩形/梯形断面需 --b 与 --n")
        p = {"b": args.b, "m": args.m or 0.0, "n": args.n}
    p["i"] = args.i

    if args.h is None and args.q is None:
        ap.error("需给 --h（正算）或 --q（反算）之一")

    print("=" * 62)
    print("河道过流能力复核（曼宁均匀流）")
    print("=" * 62)
    print("断面型式: %s   底坡 i=%.5f" % (args.shape, args.i))
    if args.shape != "compound":
        if args.n in [float(x) for x in N_REF]:
            pass
        print("糙率 n  : %.3f  ≈ %s（参考值，非规范强制）" %
              (p["n"], N_REF.get("%.3f" % p["n"], "自定义")))

    if args.h is not None:
        Q, v, Fr, R = discharge(args.shape, args.h, p)
        A, P, T = section_geom(args.shape, args.h, p)
        hc = critical_depth(args.shape, p, Q)
        print("-" * 62)
        print("水深 h    : %.3f m" % args.h)
        print("过水面积 A: %.3f m²   湿周 P: %.3f m   水力半径 R: %.3f m" % (A, P, R))
        print("水面宽 T  : %.3f m" % T)
        print("=> 过流能力 Q: %.4f m³/s" % Q)
        print("流速 v    : %.4f m/s" % v)
        print("弗劳德数 Fr: %.3f  (%s)" % (Fr, "缓流" if Fr < 1 else "急流"))
        if hc:
            print("临界水深 hc: %.3f m" % hc)
        if args.v_allow is not None:
            print("-" * 62)
            print("允许流速  : %.3f m/s  → 实际 v=%.3f → %s" % (
                args.v_allow, v, "满足" if v <= args.v_allow else "★ 冲刷风险（v > 允许值）"))
    else:
        h = solve_h(args.shape, p, args.q)
        if h is None:
            print("无法反求（流量超出该断面合理范围）")
            return 0
        Q, v, Fr, R = discharge(args.shape, h, p)
        A, P, T = section_geom(args.shape, h, p)
        hc = critical_depth(args.shape, p, args.q)
        print("-" * 62)
        print("设计流量 Q: %.4f m³/s" % args.q)
        print("=> 均匀流水深 h: %.4f m" % h)
        print("过水面积 A: %.3f m²   水力半径 R: %.3f m   水面宽 T: %.3f m" % (A, R, T))
        print("流速 v    : %.4f m/s" % v)
        print("弗劳德数 Fr: %.3f  (%s)" % (Fr, "缓流" if Fr < 1 else "急流"))
        if hc:
            print("临界水深 hc: %.3f m" % hc)
        if args.v_allow is not None:
            print("允许流速  : %.3f m/s  → %s" % (
                args.v_allow, "满足" if v <= args.v_allow else "★ 冲刷风险"))
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
