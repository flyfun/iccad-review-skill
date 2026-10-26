#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""船舶荷载（撞击能量 / 系缆力 / 挤靠力）复算（水运工程报告审查用）。

【它解决什么】
    报告常写"设计撞击力 1200kN""系缆力 800kN"，但不给能量或分力过程。本工具按
    JTS 144-1—2010 第 10 章独立复算，并核"系缆力标准值是否低于规范最小值"。

【依据】
    JTS 144-1—2010  10.4.2    E0 = ρ·m·Vn² / 2
                              E0 有效撞击能量(kJ)；ρ 有效动能系数 0.7~0.8；
                              m 船舶质量(t)，按设计船型满载排水量；Vn 法向靠岸速度(m/s)
    JTS 144-1—2010  10.4.4    表10.4.4-1 海船法向靠岸速度 / 表10.4.4-2 河船（按排水量分档）
    JTS 144-1—2010  10.2.1    N = K/n · √(ΣFx² + ΣFy²)
                              Nx = N·sinα·cosβ；Ny = N·cosα·cosβ；Nz = N·sinβ
                              K：n=2 取 1.2，n>2 取 1.3
    JTS 144-1—2010  10.2.3    系船缆夹角 α=30°（海/河船）、β=15°（海船）/0°（河船）
    JTS 144-1—2010  10.2.5    表10.2.5-1 海船系缆力标准值下限（按 DWT）
    JTS 144-1—2010  10.3.2   连续布置护舷：F = K·ΣFy / L（K=1.1）
    JTS 144-1—2010  10.3.3   间断布置护舷：F' = K'·ΣFy / n（K'=1.3）

⚠ 第 10 章**无强制性条文**（本规范 12 条强条在 5.1.1/5.2.1/5.2.2/6.1.1/7.0.x/8.0.x/11.0.6/12.0.2），
  别把本章判据误标为强条。

【用法】
    python calc_ship_loads.py --mode impact --m 45000 --vn 0.15 --rho 0.75 --absorber 900
    python calc_ship_loads.py --mode mooring --fx 320 --fy 180 --n 4 --dwt 50000 --alpha 30 --beta 15
    python calc_ship_loads.py --mode berthing --fy 320 --layout continuous --length 60

【退出码】0 满足 / 1 不满足 / 2 输入错 / 3 仅参考值
"""
import argparse
import math
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# —— 表10.2.5-1 海船系缆力标准值下限（kN）——
MOORING_MIN = [
    (1000, 150), (2000, 200), (5000, 300), (10000, 400), (20000, 500),
    (30000, 550), (50000, 650), (80000, 750), (100000, 1000), (120000, 1100),
    (150000, 1300), (200000, 1500), (250000, 2000), (300000, 2000),
]
# —— 表10.4.4-1 海船法向靠岸速度（m/s，有掩护 / 无掩护）——
VN_SEA = [
    (1000, (0.20, 0.25), (0.25, 0.45)),
    (5000, (0.15, 0.20), (0.20, 0.40)),
    (10000, (0.12, 0.17), (0.17, 0.35)),
    (30000, (0.10, 0.15), (0.15, 0.30)),
    (50000, (0.10, 0.12), (0.12, 0.25)),
    (100000, (0.08, 0.10), (0.10, 0.20)),
    (float("inf"), (0.06, 0.08), (0.08, 0.15)),
]
K_UNEVEN_CONT, K_UNEVEN_INT = 1.1, 1.3


def _fmt(v, f="%.2f"):
    return f % v if v is not None else "-"


def _check_min(name, val, lim, bad, f="%.2f", note=""):
    ok = val >= lim - 1e-9
    print("  %-24s : %s  %s 限值 %s  %s" % (
        name, _fmt(val, f), "≥" if ok else "★<", _fmt(lim, f),
        ("满足" if ok else "**不满足**") + ("  " + note if note else "")))
    if not ok:
        bad.append("%s = %s < 限值 %s" % (name, _fmt(val, f), _fmt(lim, f)))
    return ok


def _mooring_min(dwt):
    """表10.2.5-1 线性内插。"""
    if dwt <= MOORING_MIN[0][0]:
        return MOORING_MIN[0][1]
    for (d1, v1), (d2, v2) in zip(MOORING_MIN, MOORING_MIN[1:]):
        if d1 <= dwt <= d2:
            return v1 + (v2 - v1) * (dwt - d1) / (d2 - d1)
    return MOORING_MIN[-1][1]


def _vn_range(dwt, covered=True):
    for lim, cov, unc in VN_SEA:
        if dwt <= lim:
            return cov if covered else unc
    return VN_SEA[-1][1] if covered else VN_SEA[-1][2]


def main():
    ap = argparse.ArgumentParser(description="船舶荷载复算（JTS 144-1—2010 第10章）")
    ap.add_argument("--mode", required=True, choices=["impact", "mooring", "berthing"])
    ap.add_argument("--m", type=float, default=None, help="[impact] 船舶质量（满载排水量），t")
    ap.add_argument("--vn", type=float, default=None, help="[impact] 法向靠岸速度，m/s")
    ap.add_argument("--rho", type=float, default=0.75, help="[impact] 有效动能系数 0.7~0.8")
    ap.add_argument("--absorber", type=float, default=None, help="[impact] 护舷（防冲设备）吸能量，kJ")
    ap.add_argument("--fx", type=float, default=0.0, help="[mooring] 横向分力总和 ΣFx，kN")
    ap.add_argument("--fy", type=float, default=0.0, help="[mooring/berthing] 纵向分力总和 ΣFy，kN")
    ap.add_argument("--n", type=float, default=None, help="[mooring] 同时受力系船柱数目；[berthing] 护舷个数")
    ap.add_argument("--dwt", type=float, default=None, help="[mooring] 船舶载重量，用于查表10.2.5-1")
    ap.add_argument("--alpha", type=float, default=30.0, help="[mooring] 系缆水平投影与码头前沿线夹角 α，°")
    ap.add_argument("--beta", type=float, default=15.0, help="[mooring] 系缆与水平面夹角 β，°")
    ap.add_argument("--layout", default="continuous", choices=["continuous", "intermittent"],
                    help="[berthing] 护舷布置 continuous/intermittent")
    ap.add_argument("--length", type=float, default=None, help="[berthing] 船舶直线段与护舷接触长度 L，m")
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告结论值")
    args = ap.parse_args()

    bad, calc = [], None

    if args.mode == "impact":
        if not args.m or not args.vn:
            print("★ 输入错：--m 与 --vn 必填", file=sys.stderr)
            return 2
        if not (0.7 - 1e-9 <= args.rho <= 0.8 + 1e-9):
            print("★ 输入错：--rho 有效动能系数应在 0.7~0.8（10.4.2）", file=sys.stderr)
            return 2
        e0 = args.rho * args.m * args.vn ** 2 / 2.0
        calc = e0
        lo, hi = _vn_range(args.m, True)
        print("=" * 64)
        print("依据            : JTS 144-1—2010 10.4.2")
        print("船舶质量   m    : %.0f t" % args.m)
        print("法向靠岸速度 Vn : %.2f m/s  （表10.4.4-1 有掩护参考 %.2f~%.2f）" % (args.vn, lo, hi))
        print("有效动能系数 ρ  : %.2f" % args.rho)
        print("-" * 64)
        print("有效撞击能量 E0 : %.1f kJ  = %.2f×%.0f×%.3f²/2" % (e0, args.rho, args.m, args.vn))
        if args.vn < lo - 1e-9 or args.vn > hi + 1e-9:
            print("  ▲ 提示：Vn 超出有掩护码头参考区间，若为无掩护码头须按表10.4.4-1 无掩护列取值")
        if args.absorber is not None:
            print("护舷吸能量      : %.1f kJ" % args.absorber)
            ok = e0 <= args.absorber + 1e-9
            print("  %-24s : %s  %s 限值 %s  %s" % (
                "E0 vs 护舷吸能", _fmt(e0, "%.1f"), "≤" if ok else "★>",
                _fmt(args.absorber, "%.1f"), "满足" if ok else "**不满足（护舷选型偏小）**"))
            if not ok:
                bad.append("撞击能量 %.1f kJ > 护舷吸能 %.1f kJ" % (e0, args.absorber))

    elif args.mode == "mooring":
        if args.n is None or args.n < 1:
            print("★ 输入错：--n 同时受力系船柱数目必填（≥1）", file=sys.stderr)
            return 2
        k = 1.2 if args.n == 2 else 1.3
        s = math.hypot(args.fx, args.fy)
        n_val = k / args.n * s
        a, b = math.radians(args.alpha), math.radians(args.beta)
        nx = n_val * math.sin(a) * math.cos(b)
        ny = n_val * math.cos(a) * math.cos(b)
        nz = n_val * math.sin(b)
        calc = n_val
        print("=" * 64)
        print("依据            : JTS 144-1—2010 10.2.1 / 10.2.5")
        print("横向分力 ΣFx    : %.1f kN" % args.fx)
        print("纵向分力 ΣFy    : %.1f kN" % args.fy)
        print("受力系船柱 n    : %.0f    受力不均匀系数 K=%.1f" % (args.n, k))
        print("系缆夹角 α/β    : %.0f° / %.0f°" % (args.alpha, args.beta))
        print("-" * 64)
        print("系缆力标准值 N  : %.1f kN" % n_val)
        print("  横向分力 Nx   : %.1f kN" % nx)
        print("  纵向分力 Ny   : %.1f kN" % ny)
        print("  竖向分力 Nz   : %.1f kN" % nz)
        if args.dwt:
            lo = _mooring_min(args.dwt)
            print("表10.2.5-1 下限 : %.0f kN（DWT=%.0f 内插）" % (lo, args.dwt))
            _check_min("系缆力 vs 规范下限", n_val, lo, bad, f="%.1f",
                       note="10.2.5 不应小于表列数值")

    else:  # berthing
        if not args.fy:
            print("★ 输入错：--fy 横向分力总和必填", file=sys.stderr)
            return 2
        print("=" * 64)
        print("依据            : JTS 144-1—2010 10.3.2 / 10.3.3")
        print("横向分力总和 ΣFy: %.1f kN" % args.fy)
        if args.layout == "continuous":
            if not args.length:
                print("★ 输入错：连续布置须给 --length 接触长度", file=sys.stderr)
                return 2
            calc = K_UNEVEN_CONT * args.fy / args.length
            print("布置方式        : 橡胶护舷连续布置（K=%.1f）" % K_UNEVEN_CONT)
            print("挤靠力标准值 F  : %.2f kN/m" % calc)
        else:
            if not args.n:
                print("★ 输入错：间断布置须给 --n 护舷个数", file=sys.stderr)
                return 2
            calc = K_UNEVEN_INT * args.fy / args.n
            print("布置方式        : 橡胶护舷间断布置（K'=%.1f）" % K_UNEVEN_INT)
            print("单组挤靠力 F'   : %.2f kN" % calc)

    if args.report is not None and calc is not None:
        print("-" * 64)
        print("报告值          : %s" % _fmt(args.report))
        print("复算值          : %s" % _fmt(calc))
        dev = (calc - args.report) / calc * 100 if calc else 0
        print("相对偏差        : %+.1f%%" % dev)
        if abs(dev) > 5:
            print("  ▲ 提示：相对偏差超过 5%%，须核对计算过程")

    print("=" * 64)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    print("判定：满足（复算值 %s）" % _fmt(calc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
