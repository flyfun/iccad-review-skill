#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水闸过闸流量复算工具 —— 堰流 / 高淹没度堰流 / 孔流。

【它解决什么问题】
    报告里常写"过流能力 649 m³/s，满足设计流量""闸孔总净宽 42 m 满足泄流要求"。
    要判真假，得把过闸流量（或所需闸孔总净宽）自己算一遍。
    本脚本把 SL 265-2016 附录 A 的公式做成计算器：
    输入水力要素 → 出中间量 + 结果 + 适用性检查 + 与报告值比对。

【公式出处】
    SL 265-2016 附录 A「闸孔总净宽计算」。公式本体在 docx 中为**嵌入图形**
    （非 OMML、非 OLE，机器提取不到文字）。2026-10-11 从规范原始 docx 中
    逐张提取公式图片并**人工识读还原**，下列形式均据此录入：

    ── A.0.1 平底闸堰流（以堰上水头为主要因素）──
      A.0.1-1   Q  = σ·ε·m·B₀·√(2g)·H₀^1.5
                 （原式以 B₀ 表达：B₀ = Q/(σ·ε·m·√(2g)·H₀^1.5)）
      A.0.1-2   单孔闸 ε = 1 − 0.171·(1 − b₀/b_s)·⁴√(b₀/b_s)
      A.0.1-3   多孔闸 ε = [ε_z·(N−1) + ε_b] / N
      A.0.1-4   中闸孔 ε_z = 1 − 0.171·[1 − b₀/(b₀+d_z)]·⁴√[b₀/(b₀+d_z)]
      A.0.1-5   边闸孔 ε_b = 1 − 0.171·[1 − b₀/(b₀+d_z/2+b_b)]·⁴√[b₀/(b₀+d_z/2+b_b)]
      A.0.1-6   淹没系数 σ = 2.31·(h_s/H₀)·(1 − h_s/H₀)^0.4
      m（堰流流量系数，无槛平底宽顶堰）= 0.385

    ── A.0.2 平底闸高淹没度堰流（h_s/H₀ ≥ 0.9）──
      A.0.2-1   Q  = μ₀·h_s·B₀·√[2g·(H₀ − h_s)]
      A.0.2-2   μ₀ = 0.877 + (h_s/H₀ − 0.65)²

    ── A.0.3 平底闸孔流 ──
      A.0.3-1   Q  = σ′·μ·h_e·B₀·√(2g·H₀)
      A.0.3-2   μ  = φ·ε′·√(1 − ε′·h_e/H)
      A.0.3-3   ε′ = 1 / (1 + √λ·[1 − (h_c/H)²])
      A.0.3-4   λ  = 0.4 / 2.718^(16·r/h_e)     适用范围 0 < r/h_e ≤ 0.25
      φ（孔流流速系数）= 0.95~1.0
      σ′（孔流淹没系数）查表 A.0.3（按 h″/H₀ 淹没度；h″ 跃后水深）

【符号】（原文附录 A 符号表）
    B₀ 闸孔总净宽(m)｜Q 过闸流量(m³/s)｜H₀ 计入行近流速水头的堰上水深(m)
    H 堰上水深（不计行近流速水头, m）｜g 重力加速度 9.81｜m 堰流流量系数
    ε 堰流侧收缩系数｜b₀ 闸孔净宽(m)｜b_s 上游河道一半水深处宽度(m)｜N 闸孔数
    ε_z 中闸孔侧收缩系数｜d_z 中闸墩厚度(m)｜ε_b 边闸孔侧收缩系数
    b_b 边闸墩顺水流向边缘线至上游河道水边线距离(m)｜σ 堰流淹没系数
    h_s 由堰顶算起的下游水深(m)｜μ₀ 淹没堰流综合流量系数｜h_e 孔口高度(m)
    μ 孔流流量系数｜φ 孔流流速系数｜ε′ 孔流垂直收缩系数｜λ 计算系数
    r 胸墙底圆弧半径(m)｜σ′ 孔流淹没系数

【⚠️ 使用前须核对】
    ① 公式形式按原文图片识读还原，**限值/系数（m=0.385、φ=0.95~1.0、表A.0.3）实测自原文**；
       公式的**代数形式**建议与原文再核一遍（尤其孔流 A.0.3-2/-3 的 h_e 与 H 之区别）。
    ② A.0.3-3 原文图上标 h_c（疑为 h_e，孔口高度），本脚本默认取 h_e，可用 --hc 覆盖。
    ③ 系数能直接给就**直接给**（--eps/--sigma/--mu/--sigp），脚本自动算的系数仅供交叉验证。

用法示例：
    # 堰流：已知几何，求过闸流量（单孔，自由出流）
    python calc_discharge.py --mode weir --H0 2.5 --B0 6 --single-b0 6 --bs 30

    # 堰流：报告值比对（带 --reported 判满足/不满足）
    python calc_discharge.py --mode weir --H0 3.6 --B0 42 --eps 0.95 --hs 3.2 --reported 649.37

    # 高淹没度堰流（h_s/H₀≥0.9）
    python calc_discharge.py --mode weir-high --H0 4.0 --hs 3.7 --B0 42

    # 孔流（闸门控泄）：已知孔口高度，求流量
    python calc_discharge.py --mode orifice --H0 3.6 --H 3.5 --he 1.2 --B0 42 --r 0.5 --hc 1.0

    # 反算闸孔总净宽：给定设计流量 Q，求所需 B₀
    python calc_discharge.py --mode weir --H0 3.6 --Q 650 --eps 0.95
"""
import argparse
import math

G = 9.81                      # 重力加速度（SL 265 附录 A：可采用 9.81 m/s²）
M_WEIR = 0.385                # 堰流流量系数（无槛平底宽顶堰，A.0.1 正文明确）
PHI_RANGE = (0.95, 1.0)       # 孔流流速系数 φ（A.0.3）

# 表 A.0.3 孔流淹没系数 σ′（按淹没度 h″/H₀ 查；2026-10-11 实测自原文表）
SIGMA_PRIME_TABLE = [
    (0.00, 1.00), (0.10, 0.86), (0.20, 0.78), (0.30, 0.71), (0.40, 0.66),
    (0.50, 0.59), (0.60, 0.52), (0.70, 0.45), (0.80, 0.36), (0.90, 0.23),
    (0.92, 0.19), (0.94, 0.16), (0.96, 0.12), (0.98, 0.07), (0.99, 0.04),
    (0.995, 0.02),
]


# ────────────────────────── 系数计算（A.0.1 侧收缩 / A.0.1-6 淹没） ──────────────────────────
def eps_single(b0, bs):
    """A.0.1-2 单孔闸堰流侧收缩系数：ε = 1 − 0.171·(1 − b₀/b_s)·⁴√(b₀/b_s)。"""
    r = b0 / bs
    return 1 - 0.171 * (1 - r) * (r ** 0.25)


def eps_mid(b0, dz):
    """A.0.1-4 中闸孔侧收缩系数：ε_z = 1 − 0.171·[1 − b₀/(b₀+d_z)]·⁴√[b₀/(b₀+d_z)]。"""
    r = b0 / (b0 + dz)
    return 1 - 0.171 * (1 - r) * (r ** 0.25)


def eps_side(b0, dz, bb):
    """A.0.1-5 边闸孔侧收缩系数：ε_b = 1 − 0.171·[1 − b₀/(b₀+d_z/2+b_b)]·⁴√[b₀/(b₀+d_z/2+b_b)]。"""
    r = b0 / (b0 + dz / 2.0 + bb)
    return 1 - 0.171 * (1 - r) * (r ** 0.25)


def eps_multi(ez, eb, N):
    """A.0.1-3 多孔闸侧收缩系数：ε = [ε_z·(N−1) + ε_b] / N。"""
    return (ez * (N - 1) + eb) / N


def sigma_weir(hs, H0):
    """A.0.1-6 堰流淹没系数：σ = 2.31·(h_s/H₀)·(1 − h_s/H₀)^0.4。

    仅当 hs/H0 < 0.9（非高淹没度）时适用；≥0.9 应改用 A.0.2。
    """
    r = hs / H0
    return 2.31 * r * ((1 - r) ** 0.4)


def mu0_high(hs, H0):
    """A.0.2-2 淹没堰流综合流量系数：μ₀ = 0.877 + (h_s/H₀ − 0.65)²。"""
    r = hs / H0
    return 0.877 + (r - 0.65) ** 2


def lam_coef(r, he):
    """A.0.3-4 计算系数：λ = 0.4 / 2.718^(16·r/h_e)（2.718 为自然对数底 e）。"""
    return 0.4 / (2.718 ** (16.0 * r / he))


def eps_prime(hc, H, lam):
    """A.0.3-3 孔流垂直收缩系数：ε′ = 1 / (1 + √λ·[1 − (h_c/H)²])。

    注：原文该式图中下标形似 h_c，符号表列 h_e（孔口高度）；默认以 h_e 代入，
    若有收缩断面水深可用 --hc 覆盖，使用前请核对原文。
    """
    return 1.0 / (1.0 + math.sqrt(lam) * (1 - (hc / H) ** 2))


def mu_orifice(phi, ep, he, H):
    """A.0.3-2 孔流流量系数：μ = φ·ε′·√(1 − ε′·h_e/H)。"""
    return phi * ep * math.sqrt(max(0.0, 1 - ep * he / H))


def sigma_prime(ratio):
    """表 A.0.3 查 σ′（按淹没度 h″/H₀ 线性插值；≤0 取 1.00，>0.995 取 0.02）。"""
    if ratio <= SIGMA_PRIME_TABLE[0][0]:
        return SIGMA_PRIME_TABLE[0][1]
    if ratio >= SIGMA_PRIME_TABLE[-1][0]:
        return SIGMA_PRIME_TABLE[-1][1]
    for i in range(1, len(SIGMA_PRIME_TABLE)):
        x0, y0 = SIGMA_PRIME_TABLE[i - 1]
        x1, y1 = SIGMA_PRIME_TABLE[i]
        if ratio <= x1:
            return y0 + (y1 - y0) * (ratio - x0) / (x1 - x0)
    return SIGMA_PRIME_TABLE[-1][1]


# ────────────────────────── 结果输出（含报告值比对） ──────────────────────────
def report(name, value, unit, reported):
    """打印结果；若给了报告值则判满足/不满足。返回退出码（0 满足/1 不满足）。"""
    print("  ── %s = %.3f %s" % (name, value, unit))
    if reported is None:
        return 0
    diff = value - reported
    ratio = reported / value if value else 0.0
    ok = abs(diff) <= max(0.02 * value, 1e-6)   # 2% 容差视为一致
    print("  报告值 = %.3f %s，计算值 = %.3f %s，差 %.3f（%.2f%%）"
          % (reported, unit, value, unit, diff, abs(diff) / value * 100 if value else 0))
    print("  ==>> %s" % ("与计算值一致" if ok else
                         ("报告值偏小 %.3f %s" % (abs(diff), unit) if diff > 0
                          else "报告值偏大 %.3f %s" % (abs(diff), unit))))
    return 0 if ok else 1


# ────────────────────────── 三种流态的求解 ──────────────────────────
def mode_weir(a):
    """A.0.1 平底闸堰流：Q = σ·ε·m·B₀·√(2g)·H₀^1.5（或反算 B₀）。"""
    if a.H0 is None:
        raise SystemExit("--mode weir 需给 --H0（堰上总水头）")
    print("【平底闸堰流】SL 265 附录 A.0.1")
    print("  Q = σ·ε·m·B₀·√(2g)·H₀^1.5")

    # 侧收缩系数 ε
    eps = a.eps
    if eps is None:
        if a.single_b0 is not None and a.bs is not None:
            eps = eps_single(a.single_b0, a.bs)
            print("  ε（单孔,A.0.1-2）= 1−0.171(1−b₀/b_s)·⁴√(b₀/b_s) = %.4f  (b₀=%.2f,b_s=%.2f)"
                  % (eps, a.single_b0, a.bs))
        elif None not in (a.N, a.b0, a.dz, a.bb, a.bs):
            ez = eps_mid(a.b0, a.dz)
            eb = eps_side(a.b0, a.dz, a.bb)
            eps = eps_multi(ez, eb, a.N)
            print("  ε_z(A.0.1-4)=%.4f  ε_b(A.0.1-5)=%.4f" % (ez, eb))
            print("  ε（多孔,A.0.1-3）= [ε_z(N−1)+ε_b]/N = %.4f  (N=%d)" % (eps, a.N))
        else:
            raise SystemExit("需给 --eps 直接指定侧收缩系数，或给 --single-b0/--bs（单孔）"
                             "或 --N/--b0/--dz/--bb/--bs（多孔）自动计算")
    else:
        print("  ε（用户给定）= %.4f" % eps)

    # 淹没系数 σ
    sigma = a.sigma
    if sigma is None:
        if a.hs is not None:
            ratio = a.hs / a.H0
            if ratio >= 0.9:
                print("  ⚠ h_s/H₀ = %.3f ≥ 0.9 → 属**高淹没度**，应改用 --mode weir-high（A.0.2）" % ratio)
            sigma = sigma_weir(a.hs, a.H0)
            print("  σ（淹没,A.0.1-6）= 2.31(h_s/H₀)(1−h_s/H₀)^0.4 = %.4f  (h_s=%.2f)" % (sigma, a.hs))
        else:
            sigma = 1.0
            print("  σ = 1.000（未给 --hs，按自由出流取 1.0；淹没出流须给 --hs）")
    else:
        print("  σ（用户给定）= %.4f" % sigma)

    m = a.m if a.m is not None else M_WEIR
    print("  m = %.3f（无槛平底宽顶堰，A.0.1）" % m)
    c = sigma * eps * m * math.sqrt(2 * G)   # 单位水头下的流量系数
    h15 = a.H0 ** 1.5

    if a.Q is not None:      # 反算闸孔总净宽
        B0 = a.Q / (c * h15)
        print("  反算：B₀ = Q/(σ·ε·m·√(2g)·H₀^1.5)")
        print("  Q=%.3f  σ·ε·m·√(2g)=%.4f  H₀^1.5=%.4f" % (a.Q, c, h15))
        rc = report("闸孔总净宽 B₀", B0, "m", a.reported)
        print("  （第4.2.8条条文说明：采用的闸孔总净宽宜超过计算值 3%~5%）")
        return rc
    if a.B0 is None:
        raise SystemExit("--mode weir 需给 --B0（求流量）或 --Q（反算净宽）")
    Q = c * a.B0 * h15
    print("  σ·ε·m·√(2g) = %.4f    H₀^1.5 = %.4f" % (c, h15))
    return report("过闸流量 Q", Q, "m³/s", a.reported)


def mode_weir_high(a):
    """A.0.2 高淹没度堰流：Q = μ₀·h_s·B₀·√[2g(H₀−h_s)]。"""
    if None in (a.H0, a.hs):
        raise SystemExit("--mode weir-high 需给 --H0 与 --hs")
    if a.hs >= a.H0:
        raise SystemExit("需 h_s < H₀（下游水深小于堰上总水头）")
    print("【高淹没度堰流】SL 265 附录 A.0.2（h_s/H₀ ≥ 0.9）")
    print("  Q = μ₀·h_s·B₀·√[2g·(H₀ − h_s)]")
    ratio = a.hs / a.H0
    if ratio < 0.9:
        print("  ⚠ h_s/H₀ = %.3f < 0.9，严格说不属高淹没度（A.0.2 适用范围），结果仅供参考" % ratio)
    mu0 = a.mu0 if a.mu0 is not None else mu0_high(a.hs, a.H0)
    if a.mu0 is None:
        print("  μ₀（A.0.2-2）= 0.877 + (h_s/H₀ − 0.65)² = %.4f" % mu0)
    else:
        print("  μ₀（用户给定）= %.4f" % mu0)
    root = math.sqrt(2 * G * (a.H0 - a.hs))
    c = mu0 * a.hs * root
    if a.Q is not None:
        B0 = a.Q / c
        print("  反算：B₀ = Q/(μ₀·h_s·√[2g(H₀−h_s)])")
        return report("闸孔总净宽 B₀", B0, "m", a.reported)
    if a.B0 is None:
        raise SystemExit("--mode weir-high 需给 --B0 或 --Q")
    return report("过闸流量 Q", c * a.B0, "m³/s", a.reported)


def mode_orifice(a):
    """A.0.3 孔流：Q = σ′·μ·h_e·B₀·√(2g·H₀)。"""
    if a.H0 is None or a.he is None:
        raise SystemExit("--mode orifice 需给 --H0 与 --he（孔口高度）")
    print("【平底闸孔流】SL 265 附录 A.0.3")
    print("  Q = σ′·μ·h_e·B₀·√(2g·H₀)")

    H = a.H if a.H is not None else a.H0
    if a.H is None:
        print("  H 未给，按 H = H₀ = %.3f 处理（行近流速水头忽略；见 A.0.3 符号）" % H)

    # 孔流流量系数 μ
    mu = a.mu
    if mu is None:
        phi = a.phi if a.phi is not None else 0.95
        if not (PHI_RANGE[0] - 1e-9 <= phi <= PHI_RANGE[1] + 1e-9):
            print("  ⚠ φ=%.2f 超出附录 A.0.3 推荐区间 %.2f~%.2f，请复核" % (phi, *PHI_RANGE))
        lam = a.lam if a.lam is not None else (lam_coef(a.r, a.he) if a.r is not None else None)
        if lam is None:
            raise SystemExit("计算 μ 需给 --r（胸墙底圆弧半径）或直接给 --lam，或直接给 --mu")
        if a.lam is None:
            print("  λ（A.0.3-4）= 0.4/2.718^(16·r/h_e) = %.4f  (r=%.2f,h_e=%.2f)" % (lam, a.r, a.he))
            rr = a.r / a.he
            if not (0 < rr <= 0.25 + 1e-9):
                print("  ⚠ r/h_e = %.3f 超出 A.0.3-4 适用范围 0 < r/h_e ≤ 0.25，公式不适用" % rr)
        hc = a.hc if a.hc is not None else a.he
        ep = eps_prime(hc, H, lam)
        print("  ε′（A.0.3-3）= 1/(1+√λ[1−(h_c/H)²]) = %.4f  (h_c=%.2f,H=%.2f)" % (ep, hc, H))
        mu = mu_orifice(phi, ep, a.he, H)
        print("  μ（A.0.3-2）= φ·ε′·√(1−ε′h_e/H) = %.4f  (φ=%.2f)" % (mu, phi))
    else:
        print("  μ（用户给定）= %.4f" % mu)

    # 孔流淹没系数 σ′
    sigp = a.sigp
    if sigp is None:
        if a.hc2 is not None:      # 跃后水深 h″
            ratio = a.hc2 / a.H0
            sigp = sigma_prime(ratio)
            print("  σ′（表A.0.3，h″/H₀=%.3f 插值）= %.4f" % (ratio, sigp))
        else:
            sigp = 1.0
            print("  σ′ = 1.000（未给 --hc2 跃后水深，按自由孔流取 1.0；淹没孔流须给 --hc2）")
    else:
        print("  σ′（用户给定）= %.4f" % sigp)

    root = math.sqrt(2 * G * a.H0)
    c = sigp * mu * a.he * root
    if a.Q is not None:
        B0 = a.Q / c
        print("  反算：B₀ = Q/(σ′·μ·h_e·√(2g·H₀))")
        return report("闸孔总净宽 B₀", B0, "m", a.reported)
    if a.B0 is None:
        raise SystemExit("--mode orifice 需给 --B0 或 --Q")
    return report("过闸流量 Q", c * a.B0, "m³/s", a.reported)


def main():
    ap = argparse.ArgumentParser(
        description="水闸过闸流量复算（SL 265-2016 附录 A：堰流/高淹没度堰流/孔流）")
    ap.add_argument("--mode", required=True, choices=["weir", "weir-high", "orifice"],
                    help="weir 平底闸堰流(A.0.1) / weir-high 高淹没度堰流(A.0.2) / orifice 孔流(A.0.3)")
    # 水力要素
    ap.add_argument("--H0", type=float, default=None, help="计入行近流速水头的堰上水深 H₀，m")
    ap.add_argument("--H", type=float, default=None, help="堰上水深 H（不计行近流速水头），m")
    ap.add_argument("--hs", type=float, default=None, help="由堰顶算起的下游水深 h_s，m")
    ap.add_argument("--B0", type=float, default=None, help="闸孔总净宽 B₀，m")
    ap.add_argument("--Q", type=float, default=None, help="过闸流量 Q，m³/s（给了则反算 B₀）")
    ap.add_argument("--he", type=float, default=None, help="孔口高度 h_e，m")
    ap.add_argument("--hc", type=float, default=None, help="收缩断面水深（A.0.3-3 用；默认取 h_e）")
    ap.add_argument("--hc2", type=float, default=None, help="跃后水深 h″（查表 A.0.3 用）")
    ap.add_argument("--r", type=float, default=None, help="胸墙底圆弧半径 r，m")
    # 闸孔几何（算侧收缩系数）
    ap.add_argument("--N", type=int, default=None, help="闸孔数")
    ap.add_argument("--b0", type=float, default=None, help="单孔净宽 b₀，m")
    ap.add_argument("--single-b0", dest="single_b0", type=float, default=None, help="单孔闸净宽 b₀，m")
    ap.add_argument("--dz", type=float, default=None, help="中闸墩厚度 d_z，m")
    ap.add_argument("--bb", type=float, default=None, help="边墩至上游水边线距离 b_b，m")
    ap.add_argument("--bs", type=float, default=None, help="上游河道半水深宽 b_s，m")
    # 系数（给了则直接用，不自动算）
    ap.add_argument("--m", type=float, default=None, help="堰流流量系数（默认 0.385）")
    ap.add_argument("--eps", type=float, default=None, help="堰流侧收缩系数 ε")
    ap.add_argument("--sigma", type=float, default=None, help="堰流淹没系数 σ")
    ap.add_argument("--mu0", type=float, default=None, help="综合流量系数 μ₀")
    ap.add_argument("--mu", type=float, default=None, help="孔流流量系数 μ")
    ap.add_argument("--sigp", type=float, default=None, help="孔流淹没系数 σ′")
    ap.add_argument("--phi", type=float, default=None, help="孔流流速系数 φ（默认 0.95）")
    ap.add_argument("--lam", type=float, default=None, help="计算系数 λ")
    # 比对
    ap.add_argument("--reported", type=float, default=None, help="报告中的流量/B₀ 值，用于判满足")
    a = ap.parse_args()

    if a.mode == "weir":
        rc = mode_weir(a)
    elif a.mode == "weir-high":
        rc = mode_weir_high(a)
    else:
        rc = mode_orifice(a)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
