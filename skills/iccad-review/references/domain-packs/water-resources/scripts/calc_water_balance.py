#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""水量平衡复算器 —— 核"取水 / 用水 / 耗水 / 退水"四个量是否闭合（水资源论证报告审查用）。

【它解决什么】
    水资源论证报告最容易出硬错的地方不是条文引用，而是**四个水量对不上**：
      · 取水量把输水损失漏了（3.9 定义：取水量含输水损失）；
      · 退水量直接拍一个比例，与"耗水 + 退水 = 用水"打不平；
      · 分环节水量平衡表各行相加 ≠ 全项目合计。
    本工具按 GB/T 35580-2017 3.8 / 3.9 / 3.10 的水量定义独立复算，
    **不采信报告结论**，做"复算值 / 报告值"三方比对。

【依据】
    GB/T 35580-2017 3.8  水量平衡：全部水量的输入输出平衡
    GB/T 35580-2017 3.9  取水量：新水量（**包括输水损失**）总和
    GB/T 35580-2017 3.10 退水量：用水后对外排放的污水量（不含水轮机排水）
    GB/T 35580-2017 8.3.1 分析取水、用水、耗水和退水的关系，绘制水量平衡图
    GB/T 35580-2017 8.3.5 以水量平衡表逐项列出取（补）水、用水、耗水、回用水及总退水量

【三条恒等式（本工具的全部判据）】
    (1) W取 = W用 + W损                    取水量含输水损失
    (2) W用 = W耗 + W退                    用水量 = 耗水 + 退水
    (3) W取 = W耗 + W退 + W损              合并式（全系统闭合）
    比率：耗水率 = W耗/W取；退水系数 = W退/W取；损失率 = W损/W取，三者之和 = 1

【用法】
    # 单系统闭合（给任意 3 个量，反算第 4 个并校验）
    python calc_water_balance.py --mode balance --intake 1200 --loss 50 --consumption 700 --return 450
    python calc_water_balance.py --mode balance --intake 1200 --loss 50 --use 1150 --consumption 700

    # 重复利用率 / 冷却水循环率
    python calc_water_balance.py --mode reuse --intake 300 --reuse-water 2700 --report 90

    # 多环节汇总（**并联用水单元**，每行：名称,取,用,损,耗,退；单位自定，须一致）
    python calc_water_balance.py --mode sum --rows "生活,300,300,0,60,240;工业,600,600,0,150,450;灌溉,300,300,0,210,90"
    #   串联（取水→输水→灌区）不适用本模式：中间水量会被重复计入，
    #   应改用 balance 逐段核，或把输水损失并入用水单元的"损"列。

【退出码】统一语义（家族约定，勿改）
    0 = 满足
    1 = 不满足（水量不闭合 / 与报告显著不符）
    2 = 输入错
    3 = 仅参考值（信息不足，无法硬判定）

【判据方向纪律】
    本域全部为**恒等式闭合**，不是上下限型：偏差绝对值超容差即不闭合。
    容差默认 2%（报告四舍五入与单位换算的正常误差），可用 --tol 调。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _f(v, nd=2):
    return "-" if v is None else ("%%.%df" % nd) % v


def _close(name, lhs, rhs, bad, tol, note=""):
    """恒等式闭合校验：|lhs - rhs| / max(|rhs|, eps) ≤ tol。"""
    if rhs in (None, 0):
        print("  %-30s : 无法校验（基准量为 0）" % name)
        return True
    dev = abs(lhs - rhs) / abs(rhs)
    ok = dev <= tol
    print("  %-30s : 复算 %s vs 应有 %s ｜偏差 %.2f%%  %s%s" % (
        name, _f(lhs), _f(rhs), dev * 100.0,
        "闭合" if ok else "**不闭合**", ("  " + note) if note else ""))
    if not ok:
        bad.append("%s 偏差 %.2f%%（复算 %s vs 应有 %s）" % (name, dev * 100.0, _f(lhs), _f(rhs)))
    return ok


def _ratio(name, num, den, f="%.4f"):
    if not den:
        return None
    v = num / den
    print("  %-30s : %s" % (name, f % v))
    return v


def main():
    ap = argparse.ArgumentParser(description="水资源论证 · 水量平衡复算")
    ap.add_argument("--mode", required=True, choices=["balance", "reuse", "sum"])
    # balance
    ap.add_argument("--intake", type=float, default=None, help="取水量 W取（含输水损失）")
    ap.add_argument("--loss", type=float, default=None, help="输水损失 W损")
    ap.add_argument("--use", type=float, default=None, help="用水量 W用（到达用水环节）")
    ap.add_argument("--consumption", type=float, default=None, help="耗水量 W耗")
    ap.add_argument("--return", dest="ret", type=float, default=None, help="退水量 W退")
    # reuse
    ap.add_argument("--reuse-water", type=float, default=None, help="重复利用水量")
    ap.add_argument("--recycle", type=float, default=None, help="冷却水循环量")
    ap.add_argument("--makeup", type=float, default=None, help="冷却水补充水量")
    ap.add_argument("--target", type=float, default=None, help="要求的重复利用率目标（%%），可选")
    # sum
    ap.add_argument("--rows", default=None, help="多环节：名称,取,用,损,耗,退 ; 行间用分号")
    # 通用
    ap.add_argument("--report", type=float, default=None, help="[可选] 报告给出的对应结论值")
    ap.add_argument("--tol", type=float, default=0.02, help="闭合容差（相对，默认 0.02）")
    args = ap.parse_args()

    bad = []
    rc = 0

    if args.mode == "balance":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 3.8/3.9/3.10 + 8.3.1/8.3.5")
        print("恒等式：W取 = W用 + W损 ； W用 = W耗 + W退")
        print("-" * 66)
        print("  输入：取 %s ｜ 用 %s ｜ 损 %s ｜ 耗 %s ｜ 退 %s" % (
            _f(args.intake), _f(args.use), _f(args.loss), _f(args.consumption), _f(args.ret)))

        intake, use, loss = args.intake, args.use, args.loss
        cons, ret = args.consumption, args.ret

        # 反算缺失量（比强制全填更贴近报告实际——报告常只给 3 个）
        if intake is not None and loss is not None and use is None:
            use = intake - loss
            print("  → 反算用水量 W用 = W取 − W损 = %s" % _f(use))
        elif intake is not None and use is not None and loss is None:
            loss = intake - use
            print("  → 反算输水损失 W损 = W取 − W用 = %s" % _f(loss))
        elif use is not None and loss is not None and intake is None:
            intake = use + loss
            print("  → 反算取水量 W取 = W用 + W损 = %s" % _f(intake))

        if use is not None and cons is not None and ret is None:
            ret = use - cons
            print("  → 反算退水量 W退 = W用 − W耗 = %s" % _f(ret))
        elif use is not None and ret is not None and cons is None:
            cons = use - ret
            print("  → 反算耗水量 W耗 = W用 − W退 = %s" % _f(cons))

        print("-" * 66)
        checked = False
        if intake is not None and use is not None and loss is not None:
            _close("式(1) W取 = W用 + W损", intake, use + loss, bad, args.tol)
            checked = True
        if use is not None and cons is not None and ret is not None:
            _close("式(2) W用 = W耗 + W退", use, cons + ret, bad, args.tol)
            checked = True
        if intake is not None and cons is not None and ret is not None and loss is not None:
            _close("式(3) W取 = W耗+W退+W损", intake, cons + ret + loss, bad, args.tol)
            checked = True

        if not checked:
            print("  ⚠ 有效量不足 3 个对应量，无法闭合校验（rc=3）")
            rc = 3

        print("-" * 66)
        if intake:
            _ratio("耗水率 W耗/W取", cons if cons is not None else 0, intake)
            _ratio("退水系数 W退/W取", ret if ret is not None else 0, intake)
            _ratio("输水损失率 W损/W取", loss if loss is not None else 0, intake)
            if cons is not None and ret is not None and loss is not None:
                s = (cons + ret + loss) / intake
                ok = abs(s - 1.0) <= args.tol
                print("  三项之和（耗+退+损）/取 : %.4f  %s" % (s, "=1 闭合" if ok else "**≠1 不闭合**"))
                if not ok:
                    bad.append("耗水率+退水系数+损失率 = %.4f ≠ 1" % s)
            # 合理性：退水量与耗水量不应为负
            for nm, v in (("耗水量", cons), ("退水量", ret), ("输水损失", loss)):
                if v is not None and v < 0:
                    bad.append("%s 为负值 %s（量纲或口径填错）" % (nm, _f(v)))

        if args.report is not None:
            print("-" * 66)
            print("报告值 : %s" % _f(args.report))
            # 以取水量为基准与报告值比对（最常用口径）
            if intake is not None:
                dev = abs(intake - args.report) / max(abs(args.report), 1e-9)
                ok = dev <= args.tol
                print("  复算取水量 %s vs 报告 %s ｜偏差 %.2f%%  %s" % (
                    _f(intake), _f(args.report), dev * 100.0, "一致" if ok else "**不一致**"))
                if not ok:
                    bad.append("报告取水量 %s 与复算 %s 偏差 %.2f%%" % (
                        _f(args.report), _f(intake), dev * 100.0))

    elif args.mode == "reuse":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 8.4.1/8.4.2（用水水平评价，指标见表2）")
        print("-" * 66)
        if args.intake is None or args.reuse_water is None:
            print("★ 输入错：reuse 模式须同时给 --intake 与 --reuse-water")
            return 2
        denom = args.intake + args.reuse_water
        rate = args.reuse_water / denom * 100.0 if denom else 0.0
        print("  取水量（新水）      : %s" % _f(args.intake))
        print("  重复利用水量        : %s" % _f(args.reuse_water))
        print("  重复利用率          : %.2f%%   [重复利用/(重复利用+新水)]" % rate)
        if args.report is not None:
            dev = abs(rate - args.report) / max(abs(args.report), 1e-9)
            ok = dev <= max(args.tol, 0.01)
            print("  报告值              : %.2f%%  偏差 %.2f%%  %s" % (
                args.report, dev * 100.0, "一致" if ok else "**不一致**"))
            if not ok:
                bad.append("重复利用率复算 %.2f%% vs 报告 %.2f%%" % (rate, args.report))
        if args.target is not None:
            ok = rate >= args.target - 1e-9
            print("  对照目标            : %.2f%%  %s" % (args.target, "达到" if ok else "**未达到**"))
            if not ok:
                bad.append("重复利用率 %.2f%% < 目标 %.2f%%" % (rate, args.target))
        if args.recycle is not None and args.makeup is not None:
            d = args.recycle + args.makeup
            rr = args.recycle / d * 100.0 if d else 0.0
            print("  冷却水循环率        : %.2f%%   [循环/(循环+补充)]" % rr)
            print("  浓缩倍率（需水质/热平衡核定，本工具不臆算）: 须由报告给出")

    elif args.mode == "sum":
        print("=" * 66)
        print("依据 : GB/T 35580-2017 8.3.5（水量平衡表逐项列示，合计须闭合）")
        print("口径 : **并联用水单元** —— Σ取 = Σ用 + Σ损 ； Σ用 = Σ耗 + Σ退")
        print("-" * 66)
        if not args.rows:
            print("★ 输入错：sum 模式须给 --rows \"名称,取,用,损,耗,退;...\"")
            return 2
        tot = [0.0] * 5
        print("  %-12s %10s %10s %10s %10s %10s" % ("环节", "取", "用", "损", "耗", "退"))
        n = 0
        for seg in args.rows.split(";"):
            seg = seg.strip()
            if not seg:
                continue
            p = [x.strip() for x in seg.split(",")]
            if len(p) < 6:
                print("★ 行格式错（须 6 列）：%s" % seg)
                return 2
            nm = p[0]
            try:
                vals = [float(x) for x in p[1:6]]
            except ValueError:
                print("★ 行数值错：%s" % seg)
                return 2
            for i in range(5):
                tot[i] += vals[i]
            n += 1
            print("  %-12s %10s %10s %10s %10s %10s" % (
                nm, _f(vals[0], 1), _f(vals[1], 1), _f(vals[2], 1), _f(vals[3], 1), _f(vals[4], 1)))
        print("  " + "-" * 62)
        print("  %-12s %10s %10s %10s %10s %10s" % (
            "合计", _f(tot[0], 1), _f(tot[1], 1), _f(tot[2], 1), _f(tot[3], 1), _f(tot[4], 1)))
        print("-" * 66)
        _close("Σ取 = Σ用 + Σ损", tot[0], tot[1] + tot[2], bad, args.tol)
        _close("Σ用 = Σ耗 + Σ退", tot[1], tot[3] + tot[4], bad, args.tol)
        if tot[1]:
            print("  综合耗水率          : %.4f" % (tot[3] / tot[1]))
            print("  综合退水系数        : %.4f" % (tot[4] / tot[1]))
        if n == 0:
            print("★ 没有有效行")
            return 2
        if bad:
            print("  ⚠ 若表中含**串联环节**（上一环节出水＝下一环节进水），Σ 会把中间水量重复计入，")
            print("     此时应改用法 --mode balance 逐段核，或只列并联用水单元。")

    print("=" * 66)
    if bad:
        print("★ 判定：不满足 %d 项 —— %s" % (len(bad), "；".join(bad)))
        return 1
    if rc == 3:
        print("判定：参考（信息不足，未做硬判定）")
        return 3
    print("判定：满足（水量闭合）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
