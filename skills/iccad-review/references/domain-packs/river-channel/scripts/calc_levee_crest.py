#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""堤顶高程复核器 —— GB 50286-2013 §7.3 / 表 3.2.1。

【复算什么】
    堤顶高程 = 设计洪水位(或设计潮位) + 波浪爬高 R + 安全加高 A
      - 安全加高 A：按 GB 50286 表 3.2.1，由【堤防级别】+【是否允许越浪】定
      - 波浪爬高 R：可直接给（最可靠），或用 R = KΔ·Kv·Kp·R0·H 计算
        （R0 为无风时光滑护面爬高，须查 GB 50286 附录 C 图/公式，本工具不臆造）

【给报告复核什么】
    报告给的堤顶高程（或堤顶超高）是否 ≥ 按规范算出的值。不足即"不满足"。

【用法】
    # 直接给波浪爬高
    python calc_levee_crest.py --level 3 --overtopping no --design-stage 12.50 --run-up 0.85
    python calc_levee_crest.py --level 2 --overtopping yes --design-stage 8.20 --run-up 0.60 \
        --report-crest 9.30
    # 用 R = KΔ·Kv·Kp·R0·H 计算
    python calc_levee_crest.py --level 3 --overtopping no --design-stage 12.50 \
        --wave-h 1.20 --slope-m 3.0 --r0 1.45 --kd 0.80 --kv 1.16 --kp 0.92

退出码：0 = 满足 / 无报告值；1 = 报告值不足。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# GB 50286-2013 表 3.2.1 堤防工程的安全加高值 A（m）
A_NO_OVERTOP = {1: 1.0, 2: 0.8, 3: 0.7, 4: 0.6, 5: 0.5}   # 不允许越浪的堤防
A_OVERTOP = {1: 0.5, 2: 0.4, 3: 0.4, 4: 0.3, 5: 0.3}      # 允许越浪的堤防


def freeboard(level, overtopping):
    tbl = A_OVERTOP if overtopping else A_NO_OVERTOP
    return tbl[level]


def run_up(args):
    """波浪爬高 R：优先用 --run-up；否则用 R = KΔ·Kv·Kp·R0·H（需全部参数）。"""
    if args.run_up is not None:
        return args.run_up, "由 --run-up 直接给定"
    if args.wave_h is not None and args.r0 is not None:
        r = args.kd * args.kv * args.kp * args.r0 * args.wave_h
        return r, "由 R=KΔ·Kv·Kp·R0·H 计算（KΔ=%.2f Kv=%.2f Kp=%.2f R0=%.2f H=%.2f）" % (
            args.kd, args.kv, args.kp, args.r0, args.wave_h)
    return None, "缺波浪爬高参数（给 --run-up，或给 --wave-h + --r0 + 系数）"


def main():
    ap = argparse.ArgumentParser(description="堤顶高程复核（GB 50286 7.3 / 表3.2.1）")
    ap.add_argument("--level", type=int, required=True, choices=[1, 2, 3, 4, 5], help="堤防工程级别 1~5")
    ap.add_argument("--overtopping", choices=["no", "yes"], default="no",
                    help="是否允许越浪（默认 no=不允许越浪）")
    ap.add_argument("--design-stage", type=float, required=True, help="设计洪水位 / 设计潮位（m）")
    ap.add_argument("--run-up", type=float, default=None, help="波浪爬高 R（m）")
    ap.add_argument("--wave-h", type=float, default=None, help="堤前平均波高 H（m）")
    ap.add_argument("--slope-m", type=float, default=None, help="斜坡坡率 m（cotα，备用信息）")
    ap.add_argument("--r0", type=float, default=None, help="无风时光滑护面爬高 R0（须查附录C）")
    ap.add_argument("--kd", type=float, default=1.0, help="护面糙渗系数 KΔ（默认1.0光滑不透水）")
    ap.add_argument("--kv", type=float, default=1.0, help="风速影响系数 Kv（默认1.0）")
    ap.add_argument("--kp", type=float, default=1.0, help="风向影响系数 Kp（默认1.0）")
    ap.add_argument("--report-crest", type=float, default=None, help="报告给出的堤顶高程（m），用于比对")
    ap.add_argument("--report-freeboard", type=float, default=None, help="报告给出的堤顶超高 Y（m），用于比对")
    args = ap.parse_args()

    over = (args.overtopping == "yes")
    a = freeboard(args.level, over)
    r, rnote = run_up(args)

    print("=" * 62)
    print("堤顶高程复核（GB 50286-2013 §7.3 / 表 3.2.1）")
    print("=" * 62)
    print("堤防级别      : %d 级" % args.level)
    print("越浪条件      : %s" % ("允许越浪" if over else "不允许越浪"))
    print("安全加高 A    : %.2f m  (表 3.2.1)" % a)
    if args.level == 1:
        print("  提示: 1 级堤防重要堤段经论证可加大，但不得大于 1.5m（3.2.1）")
    if r is None:
        print("波浪爬高 R    : 无法确定 —— %s" % rnote)
        print("\n结论: 参数不足，无法给出堤顶高程（补齐 --run-up 或 --r0）。")
        return 0
    y = r + a
    crest = args.design_stage + y
    print("波浪爬高 R    : %.3f m  (%s)" % (r, rnote))
    print("-" * 62)
    print("堤顶超高 Y    : %.3f m  (= R + A = %.3f + %.2f)" % (y, r, a))
    print("设计水位      : %.3f m" % args.design_stage)
    print("=> 应达堤顶高程: %.3f m  (= 设计水位 + Y)" % crest)

    fail = False
    if args.report_freeboard is not None:
        ok = args.report_freeboard + 1e-9 >= y
        print("-" * 62)
        print("报告堤顶超高  : %.3f m  → %s（应 ≥ %.3f）" % (
            args.report_freeboard, "满足" if ok else "低于规范值", y))
        fail = fail or (not ok)
    if args.report_crest is not None:
        rf = args.report_crest - args.design_stage
        ok = rf + 1e-9 >= y
        print("-" * 62)
        print("报告堤顶高程  : %.3f m  (推算超高 %.3f m) → %s（应 ≥ %.3f m）" % (
            args.report_crest, rf, "满足" if ok else "低于规范值", crest))
        fail = fail or (not ok)

    print("-" * 62)
    if args.report_crest is None and args.report_freeboard is None:
        print("结论: 已算出应达堤顶高程 %.3f m（未给报告值，未做比对）" % crest)
    else:
        print("结论: %s" % ("★ 不满足 —— 报告堤顶高程/超高低于按规范复算值" if fail else "✔ 满足规范要求"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
