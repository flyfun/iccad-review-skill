#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水闸水力复算工具 —— 单宽流量 / 共轭水深 / 消力池 / 海漫。

【它解决什么问题】
    报告里常写"消力池深 1.5m，满足""共轭水深核算通过"。
    要判真假，得把跃后水深、池深、海漫长度自己算一遍。
    本脚本把这几步做成计算器：输入基本水力要素 → 出中间量 + 结果 + 判据比对。

【公式出处与形式】
    SL 265-2016 附录 A / B 给出了公式的**符号定义**，但公式本体是嵌入图形
    （机器提取不到）。本脚本按附录符号定义 + 水力学通用形式还原：
      A.0.1  过流能力（堰流）  —— 本脚本不实现主式（系数受侧收缩/淹没影响大）
      单宽流量         q  = Q / B
      矩形断面共轭水深 h2 = h1/2 · ( √(1 + 8·Fr1²) − 1 ),  Fr1 = q / √(g·h1³)
      B.1.1  消力池深度 d  = σ0·h2 − h1 − ΔZ   （σ0 水跃淹没系数 1.05~1.10）
      B.1.2  消力池长度 L  = Ls + β·Lj        （β 水跃长度校正系数 0.7~0.8）
             水跃长度 Lj（矩形断面经验式） Lj ≈ 6.9·(h2 − h1)
      B.2.1  海漫长度  Lp  = K5 · √qs · √ΔH   （√qs·√ΔH = 1~9 且消能扩散良好时适用）

【⚠️ 使用前须核对】
    ① 共轭水深、水跃长度用的是**矩形断面**公式，梯形/复式断面不适用；
    ② σ0、β、K5 等系数取值以 SL 265 附录原文表为准（K5 由表 B.2.1 查）；
    ③ 附录公式本体为图形未提取，本实现按符号定义还原，结论须复核。

用法示例：
    # 单宽流量
    python calc_hydraulics.py --mode q --Q 300 --B 24

    # 共轭水深（已知收缩水深 h1 与单宽流量 q）
    python calc_hydraulics.py --mode jump --q 12.5 --h1 0.8

    # 消力池深度（按 B.1.1）
    python calc_hydraulics.py --mode pool --q 12.5 --h1 0.8 --dz 0.2 --sigma0 1.05

    # 海漫长度（B.2.1）
    python calc_hydraulics.py --mode apron --qs 11 --dH 2.5 --K5 10

    # 消力池出口单宽流量经验判据
    python calc_hydraulics.py --mode outlet --q-outlet 14 --q-channel 8
"""
import argparse
import math

G = 9.81

# 手册/工程经验判据（**非强制条文**）：消力池出口单宽流量不宜超过渠道平均单宽流量的 1.5 倍
OUTLET_Q_RATIO_LIMIT = 1.5
# SL 265 附录 B.1.1 / B.1.2 推荐系数区间（原文正文给出）
SIGMA0_RANGE = (1.05, 1.10)   # 水跃淹没系数
BETA_RANGE = (0.70, 0.80)     # 水跃长度校正系数


def check_sigma0(s):
    lo, hi = SIGMA0_RANGE
    if not (lo - 1e-9 <= s <= hi + 1e-9):
        print("  ⚠ σ0=%.2f 超出附录 B.1.1 推荐区间 %.2f~%.2f，请复核" % (s, lo, hi))


def check_beta(b):
    lo, hi = BETA_RANGE
    if not (lo - 1e-9 <= b <= hi + 1e-9):
        print("  ⚠ β=%.2f 超出附录 B.1.2 推荐区间 %.2f~%.2f，请复核" % (b, lo, hi))


def mode_q(a):
    """q = Q / B，过闸单宽流量。"""
    q = a.Q / a.B
    print("【单宽流量】q = Q / B")
    print("  Q=%.2f m³/s  B=%.2f m  →  q=%.3f m³/(s·m)" % (a.Q, a.B, q))
    return 0, q


def mode_jump(a):
    """矩形断面共轭水深（跃后水深）。"""
    if a.h1 <= 0:
        raise ValueError("--h1 必须为正（收缩水深）")
    fr1 = a.q / math.sqrt(G * a.h1 ** 3)               # 跃前弗劳德数
    h2 = a.h1 / 2.0 * (math.sqrt(1 + 8 * fr1 ** 2) - 1)  # 共轭（跃后）水深
    print("【共轭水深】矩形断面 h2 = h1/2·(√(1+8·Fr1²) − 1)")
    print("  q=%.3f m³/(s·m)  h1(收缩水深)=%.3f m" % (a.q, a.h1))
    print("  Fr1 = q/√(g·h1³) = %.3f" % fr1)
    print("  ── 跃后水深 h2 = %.3f m" % h2)
    if fr1 < 1.7:
        print("  ⚠ Fr1<1.7，水跃为波状/弱跃，共轭水深公式适用性须复核")
    return 0, {"Fr1": fr1, "h2": h2}


def mode_pool(a):
    """消力池深度（SL 265 附录 B.1.1）：d = σ0·h2 − h1 − ΔZ。

    若只给 h1 与 q，则自动先算共轭水深 h2 再算池深。
    顺带给出水跃长度与池长参考（B.1.2）。
    """
    if a.h1 <= 0:
        raise ValueError("--h1 必须为正")
    sigma0 = a.sigma0 if a.sigma0 is not None else 1.05
    dz = a.dz if a.dz is not None else 0.0
    check_sigma0(sigma0)

    fr1 = a.q / math.sqrt(G * a.h1 ** 3)
    h2 = a.h1 / 2.0 * (math.sqrt(1 + 8 * fr1 ** 2) - 1)
    d = sigma0 * h2 - a.h1 - dz
    lj = 6.9 * (h2 - a.h1)                       # 矩形断面水跃长度经验式
    beta = (BETA_RANGE[0] + BETA_RANGE[1]) / 2   # 池长取 β 中值估算
    l_pool = (a.ls or 0.0) + beta * lj

    print("【消力池】SL 265 附录 B.1.1 / B.1.2")
    print("  q=%.3f  h1=%.3f  σ0=%.2f  ΔZ=%.2f" % (a.q, a.h1, sigma0, dz))
    print("  Fr1=%.3f  →  跃后水深 h2=%.3f m" % (fr1, h2))
    print("  公式(B.1.1)：d = σ0·h2 − h1 − ΔZ = %.2f×%.3f − %.3f − %.2f" % (sigma0, h2, a.h1, dz))
    print("  ── 消力池深度 d = %.3f m" % d)
    print("  参考：水跃长度 Lj≈%.2f m；池长 L≈Ls+β·Lj = %.2f m（β 取中值 %.2f）"
          % (lj, l_pool, beta))
    if d < 0:
        print("  ⚠ 计算池深为负：尾水/收缩水深条件可能不需下挖式消力池，须复核选型（4.4.2）")
    return 0, {"h2": h2, "d": d, "Lj": lj, "L": l_pool}


def mode_apron(a):
    """海漫长度（SL 265 附录 B.2.1）：Lp = K5·√qs·√ΔH。"""
    if a.dH is None or a.K5 is None or a.qs is None:
        raise ValueError("--mode apron 需给 --qs、--dH、--K5")
    x = math.sqrt(a.qs) * math.sqrt(a.dH)
    lp = a.K5 * x
    print("【海漫长度】SL 265 附录 B.2.1  Lp = K5·√qs·√ΔH")
    print("  qs(消力池末端单宽流量)=%.3f  ΔH=%.3f  K5=%.2f" % (a.qs, a.dH, a.K5))
    print("  √qs·√ΔH = %.3f" % x)
    if not (1.0 <= x <= 9.0):
        print("  ⚠ √qs·√ΔH=%.2f 超出 B.2.1 适用区间 1~9，公式不适用，须另择方法" % x)
    print("  ── 海漫长度 Lp = %.2f m" % lp)
    return 0, {"Lp": lp}


def mode_outlet(a):
    """消力池出口单宽流量经验判据（手册经验，非强制条文）。"""
    if a.q_outlet is None or a.q_channel is None:
        raise ValueError("--mode outlet 需给 --q-outlet 与 --q-channel")
    ratio = a.q_outlet / a.q_channel
    ok = ratio <= OUTLET_Q_RATIO_LIMIT
    print("【出口单宽流量】经验判据（手册，非强制条文）")
    print("  消力池出口单宽流量 = %.3f m³/(s·m)" % a.q_outlet)
    print("  渠道平均单宽流量   = %.3f m³/(s·m)" % a.q_channel)
    print("  ── 比值 = %.2f，限值 ≤ %.2f" % (ratio, OUTLET_Q_RATIO_LIMIT))
    print("  ==>> %s：%.2f %s %.2f" % ("满足" if ok else "不满足", ratio,
                                      "≤" if ok else ">", OUTLET_Q_RATIO_LIMIT))
    print("  注：该判据为工程经验值，审查意见写『手册推荐』，不得写成『违反规范』。")
    return (0 if ok else 1), {"ratio": ratio}


def main():
    ap = argparse.ArgumentParser(description="水闸水力复算（SL 265-2016 附录 A/B）")
    ap.add_argument("--mode", required=True,
                    choices=["q", "jump", "pool", "apron", "outlet"],
                    help="q 单宽流量 / jump 共轭水深 / pool 消力池深 / apron 海漫 / outlet 出口流量判据")
    ap.add_argument("--Q", type=float, default=None, help="过闸流量，m³/s")
    ap.add_argument("--B", type=float, default=None, help="过流宽度，m")
    ap.add_argument("--q", type=float, default=None, help="单宽流量，m³/(s·m)")
    ap.add_argument("--h1", type=float, default=None, help="收缩断面水深 h1，m")
    ap.add_argument("--dz", type=float, default=None, help="池出口水面跌落 ΔZ，m")
    ap.add_argument("--sigma0", type=float, default=None, help="水跃淹没系数 σ0（默认1.05，区间1.05~1.10）")
    ap.add_argument("--ls", type=float, default=None, help="消力池斜坡段水平投影 Ls，m")
    ap.add_argument("--qs", type=float, default=None, help="消力池末端单宽流量，m³/(s·m)")
    ap.add_argument("--dH", type=float, default=None, help="上下游水位差 ΔH，m")
    ap.add_argument("--K5", type=float, default=None, help="海漫长度计算系数 K5（表B.2.1）")
    ap.add_argument("--q-outlet", dest="q_outlet", type=float, default=None, help="消力池出口单宽流量")
    ap.add_argument("--q-channel", dest="q_channel", type=float, default=None, help="渠道平均单宽流量")
    a = ap.parse_args()

    if a.mode == "q":
        if a.Q is None or a.B is None:
            raise SystemExit("--mode q 需给 --Q 与 --B")
        rc, _ = mode_q(a)
    elif a.mode == "jump":
        if a.q is None or a.h1 is None:
            raise SystemExit("--mode jump 需给 --q 与 --h1")
        rc, _ = mode_jump(a)
    elif a.mode == "pool":
        if a.q is None or a.h1 is None:
            raise SystemExit("--mode pool 需给 --q 与 --h1")
        rc, _ = mode_pool(a)
    elif a.mode == "apron":
        rc, _ = mode_apron(a)
    else:
        rc, _ = mode_outlet(a)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
