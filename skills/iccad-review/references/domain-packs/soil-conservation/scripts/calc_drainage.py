#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截排水（排洪沟 / 截水沟 / 排水沟）水力复核器 —— 明渠均匀流 + GB 51018 表 5.6.2 设计标准。

【干什么】
    复核报告"工程措施—截排水"里最常见的一句"已做水力计算"是否站得住（块 6）：
      ① 明渠均匀流（曼宁公式）正算：给断面 + 糙率 + 纵坡 → 流量 Q、流速 v、水力半径 R、弗劳德数 Fr
      ② 由设计流量反求水深 h（二分法迭代）—— 这是审查最常用的一步
      ③ 排水标准与超高对照：GB 51018-2014 表 5.6.2（坡面截排水工程 1/2/3 级）
      ④ 允许（不冲 / 不淤）流速验算：**流速允许值须由报告/规范给定，本脚本不内置**（避免误用）
      ⑤ 断面型式：梯形（--m 为边坡系数，m=0 即矩形）/ 矩形

【公式来源】
    曼宁公式 Q = (1/n)·A·R^(2/3)·i^(1/2) —— 水力学通用均匀流公式；
    断面几何 A=(b+m·h)·h、χ=b+2h√(1+m²)、R=A/χ、B=b+2m·h（梯形）；
    设计标准/超高取 GB 51018-2014 表 5.6.2（原文提取）。

【用法】
    # 由设计流量反求水深
    python calc_drainage.py --shape trapezoid --q 2.5 --n 0.025 --i 0.005 --b 1.0 --m 1.5
    # 已知断面正算流量
    python calc_drainage.py --shape trap --h 0.6 --n 0.025 --i 0.005 --b 1.0 --m 1.5
    # 带级别：同时输出表 5.6.2 排水标准 + 超高，并校验频率
    python calc_drainage.py --shape trap --q 2.5 --n 0.025 --i 0.005 --b 1.0 --m 1.5 --grade 2 --freq 5
    # 验算允许不冲流速（用户给定）
    python calc_drainage.py --shape trap --q 2.5 --n 0.025 --i 0.005 --b 1.0 --m 1.5 --v-allow 3.0

【退出码】
    0 = 计算完成且（若给验算项）通过；1 = 流速超允许 / 频率不符标准；2 = 参数错误。
"""
import argparse
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

G = 9.81

# GB 51018-2014 表 5.6.2 坡面截排水工程设计标准：级别 → (频率下限, 频率上限, 超高m)
SUPER_ELEV = {1: (5, 10, 0.3), 2: (3, 5, 0.2), 3: (3, 3, 0.2)}

# 常用糙率参考（取用须核对设计文件或水力学手册，非规范强制值）
N_REF = {"浆砌石": 0.025, "干砌石": 0.030, "混凝土": 0.014, "钢筋混凝土": 0.014,
         "土渠(顺直)": 0.0225, "土渠(有草)": 0.030, "土工膜衬砌": 0.015}


def geom(shape, b, m, h):
    """返回 (A, 湿周 chi, 水力半径 R, 水面宽 B)。"""
    if shape == "rect":
        m = 0.0
    A = (b + m * h) * h
    chi = b + 2.0 * h * math.sqrt(1.0 + m * m)
    R = A / chi if chi > 0 else 0.0
    B = b + 2.0 * m * h
    return A, chi, R, B


def discharge(shape, b, m, h, n, i):
    A, chi, R, B = geom(shape, b, m, h)
    if A <= 0 or R <= 0:
        return 0.0, 0.0, 0.0, 0.0, B
    q = (1.0 / n) * A * (R ** (2.0 / 3.0)) * math.sqrt(i)
    v = q / A
    return q, v, A, R, B


def solve_h(shape, b, m, n, i, q, hi=20.0):
    """二分法由 Q 反求 h。"""
    lo = 1e-4
    for _ in range(300):
        mid = (lo + hi) / 2.0
        qm, _, _, _, _ = discharge(shape, b, m, mid, n, i)
        if qm > q:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def main():
    ap = argparse.ArgumentParser(description="截排水明渠水力复核（曼宁均匀流 + GB 51018 表 5.6.2）")
    ap.add_argument("--shape", default="trapezoid", choices=["trapezoid", "trap", "rect", "矩形", "梯形"])
    ap.add_argument("--b", type=float, required=True, help="底宽 b（m）")
    ap.add_argument("--m", type=float, default=1.5, help="边坡系数 m（梯形；矩形填 0）")
    ap.add_argument("--n", type=float, required=True, help="糙率 n（取用须核对设计文件）")
    ap.add_argument("--i", type=float, required=True, help="渠底纵坡 i（小数，如 0.005）")
    ap.add_argument("--q", type=float, help="设计流量 Q（m³/s）→ 反求水深 h")
    ap.add_argument("--h", type=float, help="已知水深 h（m）→ 正算流量")
    ap.add_argument("--grade", type=int, choices=[1, 2, 3], help="截排水工程级别（查表 5.6.2 排水标准 + 超高）")
    ap.add_argument("--freq", type=float, help="报告设计频率（年），校验是否落在表 5.6.2 区间")
    ap.add_argument("--v-allow", type=float, help="允许不冲流速（m/s，报告/规范给定），用于验算")
    args = ap.parse_args()

    shape = "rect" if args.shape in ("rect", "矩形") else "trapezoid"
    if args.i <= 0 or args.n <= 0 or args.b <= 0:
        print("参数错误：b、n、i 须为正数。")
        return 2
    if args.q is None and args.h is None:
        print("参数错误：须给 --q（反求水深）或 --h（正算流量）之一。")
        return 2

    rc = 0
    if args.h is not None:
        h = args.h
        q, v, A, R, B = discharge(shape, args.b, args.m, h, args.n, args.i)
        mode = "正算（已知水深）"
    else:
        h = solve_h(shape, args.b, args.m, args.n, args.i, args.q)
        q, v, A, R, B = discharge(shape, args.b, args.m, h, args.n, args.i)
        mode = "反求（已知流量）"

    fr = v / math.sqrt(G * (A / B)) if B > 0 and A > 0 else 0.0
    regime = "缓流(Fr<1)" if fr < 1 else ("临界(Fr≈1)" if abs(fr - 1) < 1e-3 else "急流(Fr>1)")

    print("== 截排水明渠水力计算（曼宁均匀流）==")
    print("   断面：%s  b=%.3f m  m=%.2f  n=%.4f  i=%.5f   模式：%s"
          % ("梯形" if shape == "trapezoid" else "矩形", args.b, (0 if shape == "rect" else args.m), args.n, args.i, mode))
    print("   水深 h = %.4f m" % h)
    print("   过水面积 A = %.4f m²   水面宽 B = %.4f m   水力半径 R = %.4f m" % (A, B, R))
    print("   流量 Q = %.4f m³/s   流速 v = %.4f m/s" % (q, v))
    print("   弗劳德数 Fr = %.3f  → %s" % (fr, regime))
    print()

    # 排水标准 / 超高
    if args.grade is not None:
        lo, hi, se = SUPER_ELEV[args.grade]
        std = ("%d 年一遇" % lo) if lo == hi else ("%d 年一遇～%d 年一遇短历时暴雨" % (lo, hi))
        print("== 设计标准（GB 51018-2014 表 5.6.2，%d 级）==" % args.grade)
        print("   排水标准：%s   断面超高：%.1f m" % (std, se))
        print("   校核水深（含超高）= %.3f m（h %.3f + 超高 %.1f）" % (h + se, h, se))
        if args.freq is not None:
            ok = lo - 1e-9 <= args.freq <= hi + 1e-9
            print("   报告设计频率 %.0f 年 → %s" % (args.freq, "符合" if ok else "★不符合（越出该级别区间）"))
            if not ok:
                rc = 1
        print()

    # 允许流速验算
    if args.v_allow is not None:
        ok = v <= args.v_allow + 1e-9
        print("== 允许不冲流速验算 ==")
        print("   实算流速 %.3f m/s ≤ 允许 %.3f m/s → %s"
              % (v, args.v_allow, "满足" if ok else "★不满足（需加大断面/放缓纵坡/衬砌）"))
        if not ok:
            rc = 1
        print()

    print("常用糙率参考（取用须核对设计文件或水力学手册，非规范强制值）：")
    print("   " + "  ".join("%s=%.4g" % (k, x) for k, x in N_REF.items()))
    print()
    print("依据：曼宁公式（水力学通用）；GB 51018-2014 表 5.6.2。")
    print("注：允许不冲/不淤流速、设计洪峰流量须按当地水文手册与渠床材料确定，本脚本不内置。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
