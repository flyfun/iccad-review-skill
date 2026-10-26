#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""泵站特征水位关系与特征扬程复核（泵站工程报告审查用）。

【它解决什么】
    泵站报告最容易错的地方，是**站上(出水池)/站下(进水池)各特征水位**之间、
    以及**由水位推出的四组特征扬程**之间的关系。报告常把扬程按"设计水位对设计水位"
    写、漏水力损失、或最高/最低扬程对调。本工具**不采信报告结论**，
    按 GB 50265 4.2/4.3 独立复算并做"复算值 / 报告值"三方比对。

【依据】
    GB 50265-2022 §4.2 特征水位 / §4.3 特征扬程：
      4.3.1 设计扬程 H设 = 进出水池设计运行水位差 + 水力损失（设计扬程下满足设计流量）
      4.3.2 平均扬程 H均 = 加权平均净扬程 ∑(Hi·Qi·ti)/∑(Qi·ti) + 损失（或平均水位差 + 损失）
      4.3.3 最高扬程 Hmax = 出水池最高运行水位 − 进水池最低运行水位 + 损失（宜）
      4.3.4 最低扬程 Hmin = 出水池最低运行水位 − 进水池最高运行水位 + 损失（宜）
    GB 50288-2016 5.4.10 同义；SL 316 5.2.2 安全鉴定须确定"各种水位组合、各特征扬程"。

【命名约定】站下 = 进水池（前池）；站上 = 出水池。

【用法】
    # 1) 校验两侧水位顺序（最高≥设计≥最低；平均在区间内）
    python calc_water_levels.py --mode order \
        --z-in-max 5.2 --z-in-des 3.8 --z-in-min 2.1 --z-in-avg 3.0 \
        --z-out-max 9.6 --z-out-des 8.2 --z-out-min 7.0 --z-out-avg 7.9

    # 2) 复算四组特征扬程（+水力损失），并与报告值比对
    python calc_water_levels.py --mode head \
        --z-in-max 5.2 --z-in-des 3.8 --z-in-min 2.1 \
        --z-out-max 9.6 --z-out-des 8.2 --z-out-min 7.0 \
        --loss 0.5 --h-des 4.9 --h-max 8.0 --h-min 2.3 --tol 0.05

    # 3) 加权平均扬程
    python calc_water_levels.py --mode head-avg --series "3.5,10,30;4.2,12,25;5.0,8,15"

【退出码】统一语义（家族约定，勿改）
    0 = 满足
    1 = 不满足（水位顺序错 / 扬程关系错 / 与报告显著不符）
    2 = 输入错（缺参数、水位非数值）
    3 = 仅参考值（本脚本不返回 3）
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOL_DEFAULT = 0.05          # 与报告值的默认允许偏差 (m)


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _line(label, val, nd=2, unit="m"):
    print("  %-30s : %s %s" % (label, _f(val, nd), unit))


# —— 关系判定：a 应 >= b（下限型关系）——
def _ge(name, a, b, bad, note=""):
    ok = a is not None and b is not None and a >= b - 1e-9
    print("  %-30s : %s %s %s   %s%s" % (
        name, _f(a), "≥" if ok else "★<", _f(b),
        "满足" if ok else "**不满足**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s: %s < %s" % (name, _f(a), _f(b)))
    return ok


def _within(name, v, lo, hi, warn, note=""):
    ok = v is not None and lo is not None and hi is not None and (lo - 1e-9) <= v <= (hi + 1e-9)
    print("  %-30s : %s ∈[%s, %s]   %s%s" % (
        name, _f(v), _f(lo), _f(hi), "满足" if ok else "▲ 超出区间", ("  " + note) if note else ""))
    if not ok:
        warn.append("%s: %s 不在 [%s, %s] 内" % (name, _f(v), _f(lo), _f(hi)))
    return ok


def _cmp_report(name, calc, report, tol, bad):
    """复算值 vs 报告值：超差 → 记入 bad（rc=1），因扬程口径错属实质性问题。"""
    if report is None:
        return
    d = abs(calc - report)
    ok = d <= tol
    print("  %-30s : 复算 %s / 报告 %s  |Δ|=%.3f %s   %s" % (
        name, _f(calc), _f(report), d, "≤" if ok else "★>", "一致" if ok else "**须核对**"))
    if not ok:
        bad.append("%s 复算 %s 与报告 %s 差 %.3f > 容差 %.3f" % (name, _f(calc), _f(report), d, tol))


def mode_order(a, bad, warn):
    print("依据               : GB 50265-2022 §4.2 特征水位取值规则")
    print("-" * 62)
    print("【站下 / 进水池水位】")
    _ge("Z站下最高 ≥ Z站下设计", a.z_in_max, a.z_in_des, bad)
    _ge("Z站下设计 ≥ Z站下最低", a.z_in_des, a.z_in_min, bad)
    if a.z_in_avg is not None:
        _within("Z站下平均 在[最低,最高]", a.z_in_avg, a.z_in_min, a.z_in_max, warn,
                "排水泵站平均水位可与设计运行水位相同")
    print("【站上 / 出水池水位】")
    _ge("Z站上最高 ≥ Z站上设计", a.z_out_max, a.z_out_des, bad)
    _ge("Z站上设计 ≥ Z站上最低", a.z_out_des, a.z_out_min, bad)
    if a.z_out_avg is not None:
        _within("Z站上平均 在[最低,最高]", a.z_out_avg, a.z_out_min, a.z_out_max, warn)
    if a.z_out_max is not None and a.z_in_max is not None:
        print("-" * 62)
        _ge("Z站上最高 ≥ Z站下最高(常理)", a.z_out_max, a.z_in_max, bad,
            "抽水站站上一般高于站下；若低于须说明（如虹吸/倒灌工况）")


def mode_head(a, bad, warn):
    print("依据               : GB 50265-2022 §4.3.1~4.3.4 特征扬程")
    need = [(a.z_out_des, "站上设计运行水位"), (a.z_in_des, "站下设计运行水位"),
            (a.z_out_max, "站上最高运行水位"), (a.z_in_min, "站下最低运行水位"),
            (a.z_out_min, "站上最低运行水位"), (a.z_in_max, "站下最高运行水位")]
    miss = [nm for v, nm in need if v is None]
    if miss:
        print("  ★ 缺少水位：%s" % "、".join(miss), file=sys.stderr)
        return 2
    loss = a.loss if a.loss is not None else 0.0
    if a.loss is None:
        warn.append("未给 --loss，按**净扬程**计算（总扬程尚需计入水力损失）")
        print("  ▲ 未给 --loss → 以下为**净扬程**（总扬程 = 净扬程 + 水力损失）")
    print("-" * 62)
    h_des = (a.z_out_des - a.z_in_des) + loss
    h_max = (a.z_out_max - a.z_in_min) + loss
    h_min = (a.z_out_min - a.z_in_max) + loss
    _line("H设计 = (站上设计-站下设计)+损失", h_des)
    _line("H最高 = (站上最高-站下最低)+损失", h_max)
    _line("H最低 = (站上最低-站下最高)+损失", h_min)
    print("-" * 62)
    print("【关系校验】")
    _ge("H最高 ≥ H设计", h_max, h_des, bad)
    _ge("H设计 ≥ H最低", h_des, h_min, bad)
    if a.h_avg is not None:
        _within("H平均 在[H最低,H最高]", a.h_avg, h_min, h_max, warn)
    print("-" * 62)
    print("【与报告值比对（容差 %.3f m）】" % a.tol)
    _cmp_report("H设计", h_des, a.h_des, a.tol, bad)
    _cmp_report("H最高", h_max, a.h_max, a.tol, bad)
    _cmp_report("H最低", h_min, a.h_min, a.tol, bad)
    if a.h_avg is not None:
        print("  %-30s : 报告 %s（平均扬程宜按加权平均核算，见 --mode head-avg）" % ("H平均", _f(a.h_avg)))


def mode_head_avg(a, bad, warn):
    print("依据               : GB 50265-2022 §4.3.2 加权平均净扬程")
    if not a.series:
        print("  ★ --mode head-avg 需要 --series \"H1,Q1,t1;H2,Q2,t2;...\"", file=sys.stderr)
        return 2
    num = den = 0.0
    rows = []
    for item in a.series.split(";"):
        item = item.strip()
        if not item:
            continue
        parts = [p for p in item.replace("，", ",").split(",") if p.strip() != ""]
        if len(parts) != 3:
            print("  ★ 序列项格式错（应为 H,Q,t）：%s" % item, file=sys.stderr)
            return 2
        h, q, t = (float(parts[0]), float(parts[1]), float(parts[2]))
        num += h * q * t
        den += q * t
        rows.append((h, q, t))
    if den <= 0:
        print("  ★ ∑(Q·t) = 0，无法计算", file=sys.stderr)
        return 2
    h_avg = num / den
    print("  时段数            : %d" % len(rows))
    for h, q, t in rows:
        print("    H=%-7s Q=%-7s t=%-7s" % (_f(h), _f(q), _f(t)))
    print("  %-30s : %s m   (= ∑(H·Q·t)/∑(Q·t))" % ("加权平均净扬程 H均", _f(h_avg, 3)))
    print("  ▲ 总平均扬程 = 净扬程 + 水力损失；平均扬程下水泵应在高效区运行（4.3.2）。")
    if a.report is not None:
        print("-" * 62)
        _cmp_report("H均", h_avg, a.report, a.tol, bad)


def main():
    ap = argparse.ArgumentParser(description="泵站特征水位关系与特征扬程复核")
    ap.add_argument("--mode", required=True, choices=["order", "head", "head-avg"])
    # 站下 / 进水池
    ap.add_argument("--z-in-max", type=float, dest="z_in_max", help="站下(进水池)最高运行水位 (m)")
    ap.add_argument("--z-in-des", type=float, dest="z_in_des", help="站下(进水池)设计运行水位 (m)")
    ap.add_argument("--z-in-min", type=float, dest="z_in_min", help="站下(进水池)最低运行水位 (m)")
    ap.add_argument("--z-in-avg", type=float, dest="z_in_avg", help="站下(进水池)平均水位 (m)")
    # 站上 / 出水池
    ap.add_argument("--z-out-max", type=float, dest="z_out_max", help="站上(出水池)最高运行水位 (m)")
    ap.add_argument("--z-out-des", type=float, dest="z_out_des", help="站上(出水池)设计运行水位 (m)")
    ap.add_argument("--z-out-min", type=float, dest="z_out_min", help="站上(出水池)最低运行水位 (m)")
    ap.add_argument("--z-out-avg", type=float, dest="z_out_avg", help="站上(出水池)平均水位 (m)")
    # 损失与报告值
    ap.add_argument("--loss", type=float, default=None, help="总水力损失 (m)；缺省按净扬程计算")
    ap.add_argument("--h-des", type=float, default=None, help="[报告] 设计扬程 (m)")
    ap.add_argument("--h-max", type=float, default=None, help="[报告] 最高扬程 (m)")
    ap.add_argument("--h-min", type=float, default=None, help="[报告] 最低扬程 (m)")
    ap.add_argument("--h-avg", type=float, default=None, help="报告平均扬程 (m)")
    ap.add_argument("--series", help="加权平均用：\"H1,Q1,t1;H2,Q2,t2;...\"")
    ap.add_argument("--report", type=float, default=None, help="[报告] 单一结论值（head-avg 用）")
    ap.add_argument("--tol", type=float, default=TOL_DEFAULT, help="与报告值允许偏差 (m)，默认 0.05")
    args = ap.parse_args()

    bad, warn = [], []
    print("=" * 62)
    if args.mode == "order":
        rc = mode_order(args, bad, warn)
    elif args.mode == "head":
        rc = mode_head(args, bad, warn)
    else:
        rc = mode_head_avg(args, bad, warn)
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
