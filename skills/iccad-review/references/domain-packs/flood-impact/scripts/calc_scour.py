#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""河道冲刷深度复算 —— 支撑"冲刷与淤积影响评价""水工程安全影响评价"。

【判定依据】SL/T 808-2025 附录 A.3（冲刷与淤积分析计算），引用 GB 50707 附录 B/C、
    GB 50286 附录 D：
    A.3.3  河道冲刷深度是**河道演变冲刷、一般冲刷和局部冲刷的叠加**，
           应分析确定最大冲刷深度和冲刷线高程。
    A.3.4-1  水流平行岸坡产生的冲刷深度：
               h_B = h_p [ (v_p / v_H)^n − 1 ]        n 一般取 1/4（1/4~1/6）
                  h_B 局部冲刷深度(m)；h_p 冲刷处的水深(m)；
                  v_H 河床允许的不冲流速(m/s)；v_p 建后计算水位时主河槽平均流速(m/s)
    A.3.4-2  水流斜冲防护岸坡产生的冲刷深度（α 为水流与岸坡交角、
               m 为迎水面边坡系数、d 为坡脚处土计算粒径、V_j 为局部冲刷流速）
    A.3.4-3/-4  局部冲刷流速 V_j：
               滩地河床 V_j = β · Q₁ / (B₁ · H₁)   （B₁ 河滩宽、Q₁ 河滩流量、
                                                    H₁ 河滩水深、β 流速不均匀系数）
               无滩地河床 V_j = Q / (W − W_P)       （W 原过水面积、W_P 缩窄段面积）
    A.3.4-5~8  丁坝冲刷（另有专门公式，本工具不复算 —— 见 flood_tables.md）
    A.3.5  桥梁下一般冲刷与局部冲刷按 TB 10017 / JTG C30 计算（公式本体为图片，
           本工具不复算，报告须给出计算书）
    A.4.3  河床稳定性 ζ 系数（按河床类型取 B/h 值；★原文 OCR 残缺，本工具标"待核"）
    A.4.4  河流稳定性指标 K = D/(hJ)（D 泥沙代表粒径、h 河道平均水深、J 河道比降），
           数值越大河流相对越稳定（长江汉口段 0.924、黄河秦厂段 0.168）

【结构埋深判定依据】
    5.2.5    桥墩承台顶高程不应高于规划河底高程，不宜高于冲刷线高程
    5.3.2-3  穿越河槽及滩地段管顶埋深应在最大冲刷线以下并满足规范要求
    5.3.2-5  挖沟法施工的，管顶高程应低于最大冲刷线或规划河底高程
    5.5.5-1  蓄滞洪区内埋地敷设管道，埋深应在最大冲刷线以下

【模式】
    parallel   平行岸坡冲刷深度（式 A.3.4-1，可复算 + 可与报告值比对）
    oblique    斜冲岸坡冲刷深度（★公式本体为图片，系数按行业通用式还原，仅作量级参考）
    vj-beach   滩地河床局部冲刷流速（式 A.3.4-3）
    vj-nobank  无滩地河床局部冲刷流速（式 A.3.4-4）
    check      结构埋深/承台高程 vs 最大冲刷线高程 → 判定
    regime     河势稳定：河流稳定性指标 K = D/(hJ) + 河床稳定性 ζ 系数（附录 A.4）

【用法】
    python calc_scour.py --mode parallel --hp 4.2 --vp 2.6 --v-allowed 0.9 --report-depth 2.1
    python calc_scour.py --mode vj-beach --q1 120 --b1 60 --h1 1.8 --beta 1.25
    python calc_scour.py --mode vj-nobank --q 1500 --w 620 --wp 540
    python calc_scour.py --mode check --scour-elev 3.20 --struct-elev 2.85 --what 管顶
    python calc_scour.py --mode regime --d 0.02 --h 8.0 --j 0.00015 --bed 一般沙河

【退出码】0 = 满足/无异常；1 = 不满足或与报告显著不符；2 = 输入错误；3 = 参考值（不做判定）
"""
import argparse
import math
import sys


def main():
    ap = argparse.ArgumentParser(description="河道冲刷深度复算（SL/T 808-2025 附录 A.3）")
    ap.add_argument("--mode", required=True,
                    choices=["parallel", "oblique", "vj-beach", "vj-nobank", "check", "regime"])
    # parallel
    ap.add_argument("--hp", type=float, help="冲刷处水深 (m)")
    ap.add_argument("--vp", type=float, help="建后计算水位时主河槽平均流速 (m/s)")
    ap.add_argument("--v-allowed", type=float, help="河床允许不冲流速 v_H (m/s)")
    ap.add_argument("--n", type=float, default=0.25, help="形状指数 n（默认 0.25，可取 1/4~1/6）")
    # oblique
    ap.add_argument("--alpha", type=float, help="水流流向与岸坡交角 α (°)")
    ap.add_argument("--m", type=float, help="防护建筑物迎水面边坡系数 m")
    ap.add_argument("--d", type=float, help="坡脚处土计算粒径 d (m)")
    ap.add_argument("--vj", type=float, help="水流局部冲刷流速 V_j (m/s)")
    # vj
    ap.add_argument("--q1", type=float, help="通过河滩部分的设计流量 Q₁ (m³/s)")
    ap.add_argument("--b1", type=float, help="河滩宽度 B₁（河槽边缘至坡脚）(m)")
    ap.add_argument("--h1", type=float, help="河滩水深 H₁ (m)")
    ap.add_argument("--beta", type=float, default=1.0, help="水流流速分配不均匀系数 β（查表 A.3.4-2）")
    ap.add_argument("--q", type=float, help="设计流量 Q (m³/s)")
    ap.add_argument("--w", type=float, help="原河道过水断面面积 W (m²)")
    ap.add_argument("--wp", type=float, help="河道缩窄部分断面面积 W_P (m²)")
    # regime
    ap.add_argument("--h", type=float, help="[regime] 河道平均水深 h (m)")
    ap.add_argument("--j", type=float, help="[regime] 河道比降 J")
    ap.add_argument("--bed", default=None, help="[regime] 河床类型：砂河床 / 一般沙河 / 极易冲刷细沙河床")
    # 比对 / 判定
    ap.add_argument("--report-depth", type=float, default=None, help="[可选] 报告给出的冲刷深度 (m)")
    ap.add_argument("--scour-elev", type=float, default=None, help="[check] 最大冲刷线高程 (m)")
    ap.add_argument("--struct-elev", type=float, default=None, help="[check] 结构底（管顶/承台底/基础底）高程 (m)")
    ap.add_argument("--what", default="结构底", help="[check] 被核对象名称，如 管顶/承台底/基础底")
    args = ap.parse_args()

    print("=" * 60)
    print("冲刷深度复核（SL/T 808-2025 附录 A.3，引 GB 50707 / GB 50286 / TB 10017）")
    print("=" * 60)

    rc = 0

    if args.mode == "parallel":
        for k in ("hp", "vp", "v_allowed"):
            if getattr(args, k) is None:
                print("输入错误：parallel 需 --hp --vp --v-allowed", file=sys.stderr)
                return 2
        if args.v_allowed <= 0 or args.hp <= 0:
            print("输入错误：hp、v_H 须为正", file=sys.stderr)
            return 2
        ratio = (args.vp / args.v_allowed) ** args.n - 1.0
        hb = args.hp * ratio
        print("式(A.3.4-1)  h_B = h_p·[(v_p/v_H)^n − 1]")
        print("  h_p = %.3f m   v_p = %.3f m/s   v_H = %.3f m/s   n = %.4f" % (args.hp, args.vp, args.v_allowed, args.n))
        print("  (v_p/v_H)^n − 1 = %.4f" % ratio)
        print("  局部冲刷深度 h_B = %.3f m" % hb)
        if ratio <= 0:
            print("  ⚠ v_p ≤ v_H 得非正值 —— 说明按该允许不冲流速不应起冲；核对 v_H 取值口径。")
        out = hb
    elif args.mode == "oblique":
        for k in ("alpha", "m", "d", "vj"):
            if getattr(args, k) is None:
                print("输入错误：oblique 需 --alpha --m --d --vj", file=sys.stderr)
                return 2
        g = 9.81
        dh = 23.0 * math.tan(math.radians(args.alpha) / 2.0) / math.sqrt(1.0 + args.m ** 2) \
            * (args.vj ** 2 / g) - 30.0 * args.d
        print("式(A.3.4-2)  Δh_p = [23·tan(α/2)/√(1+m²)]·(V_j²/g) − 30d")
        print("  α = %.1f°  m = %.2f  d = %.4f m  V_j = %.3f m/s" % (args.alpha, args.m, args.d, args.vj))
        print("  斜冲局部冲刷深度 Δh_p = %.3f m" % dh)
        print("  ★ 待核：该式公式本体在原文中为图片，本工具按行业通用式（黄河/长江常用）还原，")
        print("    系数 23、30 须与原图核对后方可作为判定依据。")
        if dh < 0:
            print("  ⚠ 结果为负 —— 粒径项 30d 占优，通常表示该流速下不起冲。")
        print("=" * 60)
        return 3
    elif args.mode == "vj-beach":
        for k in ("q1", "b1", "h1"):
            if getattr(args, k) is None:
                print("输入错误：vj-beach 需 --q1 --b1 --h1（可选 --beta）", file=sys.stderr)
                return 2
        if args.b1 <= 0 or args.h1 <= 0:
            print("输入错误：B₁、H₁ 须为正", file=sys.stderr)
            return 2
        vj = args.beta * args.q1 / (args.b1 * args.h1)
        print("式(A.3.4-3)  V_j = β·Q₁/(B₁·H₁)")
        print("  Q₁ = %.1f m³/s  B₁ = %.2f m  H₁ = %.3f m  β = %.2f" % (args.q1, args.b1, args.h1, args.beta))
        print("  局部冲刷流速 V_j = %.4f m/s" % vj)
        out = vj
    elif args.mode == "vj-nobank":
        for k in ("q", "w", "wp"):
            if getattr(args, k) is None:
                print("输入错误：vj-nobank 需 --q --w --wp", file=sys.stderr)
                return 2
        if args.w - args.wp <= 0:
            print("输入错误：W − W_P 须为正（缩窄后仍有净过水面积）", file=sys.stderr)
            return 2
        vj = args.q / (args.w - args.wp)
        print("式(A.3.4-4)  V_j = Q/(W − W_P)")
        print("  Q = %.1f m³/s  W = %.1f m²  W_P = %.1f m²" % (args.q, args.w, args.wp))
        print("  局部冲刷流速 V_j = %.4f m/s" % vj)
        out = vj
    elif args.mode == "regime":
        zeta_tbl = {"砂河床": 1.4, "一般沙河": 2.75, "极易冲刷细沙河床": 5.5}
        if args.bed is not None and args.bed not in zeta_tbl:
            print("输入错误：--bed 取 砂河床 / 一般沙河 / 极易冲刷细沙河床", file=sys.stderr)
            return 2
        if args.d is not None and args.h is not None and args.j is not None:
            if args.h <= 0 or args.j <= 0:
                print("输入错误：h、J 须为正", file=sys.stderr)
                return 2
            K = args.d / (args.h * args.j)
            print("式(A.4.4)  河流稳定性指标 K = D/(h·J)")
            print("  D = %.4f m   h = %.3f m   J = %.6f" % (args.d, args.h, args.j))
            print("  K = %.4f" % K)
            print("  参考：长江汉口段 0.924、黄河秦厂段 0.168 —— **K 越大河流相对越稳定**；")
            print("        K 偏小时应重点分析河床演变趋势与冲淤幅度。")
        else:
            print("式(A.4.4)  河流稳定性指标 K = D/(h·J)（未给全 --d/--h/--j，仅列式与参考值）")
            print("  参考：长江汉口段 0.924、黄河秦厂段 0.168（K 越大越稳定）")
        if args.bed is not None:
            print("-" * 60)
            print("河床稳定性 ζ 系数（附录 A.4.3，按河床类型）")
            print("  河床类型 : %s   →  ζ = %.2f" % (args.bed, zeta_tbl[args.bed]))
            print("  ★ 待核：该条在自带条文库中 OCR 残缺（仅存\"取 2.75\"\"极易冲刷的细沙河床取\"等"
                  "片段），数值须与 SL/T 808-2025 附录 A.4.3 原文核对。")
        print("★ 说明：河势稳定属**定性＋定量综合判断**，本模式只给指标与参考值，不作满足/不满足判定。")
        print("=" * 60)
        return 0
    else:  # check
        if args.scour_elev is None or args.struct_elev is None:
            print("输入错误：check 需 --scour-elev --struct-elev", file=sys.stderr)
            return 2
        print("[埋深判定] %s高程 = %.3f m；最大冲刷线高程 = %.3f m" % (args.what, args.struct_elev, args.scour_elev))
        if args.struct_elev <= args.scour_elev:
            print("判定：满足 —— %s高程低于最大冲刷线 %.3f m（满足埋设/承台高程要求）"
                  % (args.what, args.scour_elev - args.struct_elev))
            rc = 0
        else:
            print("★ 判定：不满足 —— %s高程高于最大冲刷线 %.3f m，"
                  "须加埋深或改承台高程（依据 SL/T 808-2025 5.2.5 / 5.3.2 / 5.5.5）"
                  % (args.what, args.struct_elev - args.scour_elev))
            rc = 1
        print("=" * 60)
        return rc

    if args.report_depth is not None:
        dev = out - args.report_depth
        print("-" * 60)
        print("报告给出冲刷深度 : %.3f m" % args.report_depth)
        print("复算 − 报告      : %+.3f m" % dev)
        if args.report_depth < out - 1e-6:
            print("★ 报告值小于复算值 —— 若报告据此确定护脚埋深/备石量，存在偏不安全风险，"
                  "须核对流场、粒径、允许流速取值。")
            rc = 1
        else:
            print("报告值不小于复算值，方向合理；仍须核对其流场与参数来源。")
    print("=" * 60)
    return rc


if __name__ == "__main__":
    sys.exit(main())
