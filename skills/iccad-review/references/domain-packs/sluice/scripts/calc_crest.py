#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
闸顶高程复核（SL 265-2016）

【用途】
    水闸报告审查时，复核报告给出的闸顶高程是否满足规范要求。
    依据 SL 265-2016 第 4.2.4 条及其配套条文（条款号均经规范库核对，
    见 references/sluice_clauses.json）：
      · 4.2.4  闸顶计算高程应根据挡水和泄水运用情况确定，取大值；
               安全加高下限值查表 4.2.4。
      · 4.2.5  位于防洪、挡潮堤上的水闸，闸顶高程不应低于防洪、挡潮堤堤顶高程。
      · 4.2.6  还应考虑：软弱地基上闸基沉降；多泥沙河流上下游河道变化引起
               水位升降；防洪、挡潮堤上水闸两侧堤顶可能加高。
      · 4.2.19 露顶式闸门顶部宜在可能出现的最高挡水位以上留有不少于 0.3m 的加高。
      · 4.2.21 闸室胸墙：孔径<=6m 可采用板式，孔径>6m 宜采用板梁式；胸墙顶宜与闸顶齐平。
      · 4.2.22 工作桥、检修便桥、交通桥的梁(板)底高程均应高出最高洪水位 0.5m 以上；
               若有流冰，应高出流冰面以上 0.2m；有通航要求时，应满足通航净空要求。

【公式】（SL 265-2016 第 4.2.4 条）
    挡水：▽顶 >= max( ▽正常蓄水位 + R正 + A正 , ▽最高挡水位 + R挡 + A挡 )
    泄水：▽顶 >= max( ▽设计洪水位 + R设 + A设 , ▽校核洪水位 + R校 + A校 )
    最终取两种运用情况的大值。
    其中：
      R —— 波浪计算高度（= 波浪中心线高出静水位 + 波浪高度，由报告风浪计算给出）；
      A —— 安全加高下限值（按工程级别和运用工况查表 4.2.4）。

【安全加高表 4.2.4】（单位：m；与 references/sluice_tables.md 一致）
    挡水·正常蓄水位 : 1级 0.7  2级 0.5  3级 0.4  4/5级 0.3
    挡水·最高挡水位 : 1级 0.5  2级 0.4  3级 0.3  4/5级 0.2
    泄水·设计洪水位 : 1级 1.5  2级 1.0  3级 0.7  4/5级 0.5
    泄水·校核洪水位 : 1级 1.0  2级 0.7  3级 0.5  4/5级 0.4

【用法示例】
    # 用户图上例题：1级闸，泄水工况，设计洪水位 123.00、校核洪水位 123.40，
    # 工作桥梁高 1.10、交通桥梁高 0.90（标准答案 125.00m）
    python calc_crest.py --level 1 --zw-design 123.00 --zw-check 123.40 \\
        --bridges "工作桥:1.10,交通桥:0.90" --reported 125.00

    # 挡水工况（含波浪）
    python calc_crest.py --level 2 --zw-normal 12.00 --rw-normal 0.30 \\
        --zw-max 11.50 --rw-max 0.25

    # 防洪堤上的水闸（叠加 4.2.5 堤顶高程约束）
    python calc_crest.py --level 3 --zw-design 45.00 --dike-crest 46.20

【退出码】0=满足（或仅给出建议值）；1=不满足；2=参数不足

【注意】
    · 安全加高 A 查自规范原文表 4.2.4（可靠）；闸顶高程公式源自条文文字（可靠）。
    · 波浪计算高度 R 由报告风浪计算提供，本脚本不自行推算波浪。
    · 4.2.6 的三项因素（沉降、河道变化、堤顶加高）为定性要求，
      不能自动量化，审查时须结合报告逐项人工判断。
"""

import argparse
import sys

# ---- 表 4.2.4 水闸安全加高下限值（单位：m）---------------------------------
# key: 运用工况；value: 按 [1级, 2级, 3级, 4/5级] 排列的加高值
SAFETY_FREEBOARD = {
    "normal":  [0.7, 0.5, 0.4, 0.3],   # 挡水·正常蓄水位
    "max":     [0.5, 0.4, 0.3, 0.2],   # 挡水·最高挡水位
    "design":  [1.5, 1.0, 0.7, 0.5],   # 泄水·设计洪水位
    "check":   [1.0, 0.7, 0.5, 0.4],   # 泄水·校核洪水位
}

# 工况中文名，用于输出
COND_NAME = {
    "normal": "挡水·正常蓄水位",
    "max":    "挡水·最高挡水位",
    "design": "泄水·设计洪水位",
    "check":  "泄水·校核洪水位",
}


def freeboard(kind, level):
    """按运用工况 kind 和工程级别 level(1~5) 取安全加高下限值（表 4.2.4）。"""
    idx = 0 if level == 1 else 1 if level == 2 else 2 if level == 3 else 3
    return SAFETY_FREEBOARD[kind][idx]


def parse_bridges(text):
    """解析 --bridges 参数。

    格式：名称:梁高,名称:梁高  (如 '工作桥:1.10,交通桥:0.90')
    兼容半角/全角冒号与逗号。返回 [(名称, 梁高), ...]
    """
    out = []
    if not text:
        return out
    text = text.replace("；", ",").replace(";", ",").replace("，", ",")
    for item in text.split(","):
        item = item.strip().replace("：", ":")
        if not item:
            continue
        if ":" not in item:
            raise ValueError("桥的参数格式应为 名称:梁高，实际收到 '%s'" % item)
        name, h = item.split(":", 1)
        out.append((name.strip(), float(h)))
    return out


def main():
    ap = argparse.ArgumentParser(
        description="闸顶高程复核（SL 265-2016 第 4.2.4 条及配套条文）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--level", type=int, required=True,
                    help="水闸工程级别 1~5（决定安全加高，表 4.2.4）")

    # ---- 挡水工况：正常蓄水位 / 最高挡水位 ----
    ap.add_argument("--zw-normal", type=float, help="挡水·正常蓄水位 ▽正，m")
    ap.add_argument("--rw-normal", type=float, default=0.0,
                    help="正常蓄水位相应波浪计算高度 R，m（默认0）")
    ap.add_argument("--zw-max", type=float, help="挡水·最高挡水位 ▽挡，m")
    ap.add_argument("--rw-max", type=float, default=0.0,
                    help="最高挡水位相应波浪计算高度 R，m（默认0）")

    # ---- 泄水工况：设计洪水位 / 校核洪水位 ----
    ap.add_argument("--zw-design", type=float, help="泄水·设计洪水位 ▽设，m")
    ap.add_argument("--rw-design", type=float, default=0.0,
                    help="设计洪水位相应波浪计算高度 R，m（默认0）")
    ap.add_argument("--zw-check", type=float, help="泄水·校核洪水位 ▽校，m")
    ap.add_argument("--rw-check", type=float, default=0.0,
                    help="校核洪水位相应波浪计算高度 R，m（默认0）")

    # ---- 附加复核项 ----
    ap.add_argument("--flood-level-max", type=float,
                    help="最高洪水位，m（供 4.2.22 桥梁复核；缺省取校核洪水位）")
    ap.add_argument("--bridges",
                    help="桥的梁(板)高，格式 名称:梁高,...（4.2.22，如 工作桥:1.10,交通桥:0.90）")
    ap.add_argument("--gate-open", action="store_true",
                    help="闸门为露顶式（触发 4.2.19 门顶超高复核）")
    ap.add_argument("--zw-impound-max", type=float,
                    help="最高挡水位，m（4.2.19 露顶闸门复核用；缺省取 --zw-max）")
    ap.add_argument("--dike-crest", type=float,
                    help="防洪/挡潮堤堤顶高程，m（4.2.5）")
    ap.add_argument("--reported", type=float,
                    help="报告采用的闸顶高程，m（传入则自动判定满足/不满足）")

    args = ap.parse_args()

    if not (1 <= args.level <= 5):
        print("错误：--level 应为 1~5")
        return 2

    # 收集各工况要求的最低闸顶高程：(标签, 值, 依据)
    reqs = []            # 参与"闸顶高程"取大值的约束
    side_checks = []     # 旁证条目（不并入闸顶高程，如露顶门顶）

    print("【闸顶高程复核】SL 265-2016 第 4.2.4 条（安全加高查表 4.2.4）")
    print("  工程级别 = %d 级" % args.level)
    print()

    # ---- 挡水工况 ----
    guard = []
    if args.zw_normal is not None:
        a = freeboard("normal", args.level)
        v = args.zw_normal + args.rw_normal + a
        guard.append(v)
        print("── 挡水工况（4.2.4）")
        print("   正常蓄水位 %.2f + 波浪 %.2f + 安全加高 %.2f = %.2f"
              % (args.zw_normal, args.rw_normal, a, v))
    if args.zw_max is not None:
        a = freeboard("max", args.level)
        v = args.zw_max + args.rw_max + a
        guard.append(v)
        if args.zw_normal is None:
            print("── 挡水工况（4.2.4）")
        print("   最高挡水位 %.2f + 波浪 %.2f + 安全加高 %.2f = %.2f"
              % (args.zw_max, args.rw_max, a, v))
    if guard:
        print("   挡水控制值 = %.2f" % max(guard))
        reqs.append(("挡水工况", max(guard), "SL 265 4.2.4"))
        print()

    # ---- 泄水工况 ----
    release = []
    if args.zw_design is not None:
        a = freeboard("design", args.level)
        v = args.zw_design + args.rw_design + a
        release.append(v)
        print("── 泄水工况（4.2.4）")
        print("   设计洪水位 %.2f + 波浪 %.2f + 安全加高 %.2f = %.2f"
              % (args.zw_design, args.rw_design, a, v))
    if args.zw_check is not None:
        a = freeboard("check", args.level)
        v = args.zw_check + args.rw_check + a
        release.append(v)
        if args.zw_design is None:
            print("── 泄水工况（4.2.4）")
        print("   校核洪水位 %.2f + 波浪 %.2f + 安全加高 %.2f = %.2f"
              % (args.zw_check, args.rw_check, a, v))
    if release:
        print("   泄水控制值 = %.2f" % max(release))
        reqs.append(("泄水工况", max(release), "SL 265 4.2.4"))
        print()

    if not reqs and not side_checks and args.dike_crest is None:
        print("错误：至少应给出一个水位参数（--zw-normal / --zw-max / --zw-design / --zw-check）")
        return 2

    # ---- 4.2.22 桥梁梁(板)底高程复核 ----
    flood_max = args.flood_level_max
    if flood_max is None:
        flood_max = args.zw_check  # 缺省以校核洪水位为最高洪水位
    bridges = parse_bridges(args.bridges)
    if bridges:
        if flood_max is None:
            print("提示：未给出 --flood-level-max，且无 --zw-check，跳过桥梁复核（4.2.22）")
        else:
            print("── 桥梁梁(板)底高程复核（4.2.22）最高洪水位 = %.2f" % flood_max)
            for name, h in bridges:
                # 梁底 = 桥面 - 梁高；要求 梁底 >= 最高洪水位 + 0.5
                # => 桥面(=闸顶) >= 最高洪水位 + 梁高 + 0.5
                need = flood_max + h + 0.5
                reqs.append(("%s（梁高%.2f）" % (name, h), need, "SL 265 4.2.22"))
                print("   %s：桥面(闸顶) >= %.2f + %.2f + 0.50 = %.2f"
                      % (name, flood_max, h, need))
            print()

    # ---- 4.2.5 防洪/挡潮堤 ----
    if args.dike_crest is not None:
        reqs.append(("防洪/挡潮堤堤顶", args.dike_crest, "SL 265 4.2.5"))
        print("── 防洪/挡潮堤上水闸（4.2.5）闸顶 >= 堤顶高程 %.2f" % args.dike_crest)
        print()

    # ---- 4.2.19 露顶式闸门门顶超高（旁证，不并入闸顶高程）----
    if args.gate_open:
        zw_imp = args.zw_impound_max
        if zw_imp is None:
            zw_imp = args.zw_max
        if zw_imp is None:
            print("提示：露顶式闸门复核需要 --zw-impound-max 或 --zw-max，已跳过（4.2.19）")
        else:
            need_gate = zw_imp + 0.3
            side_checks.append(("露顶式闸门门顶", need_gate, "SL 265 4.2.19"))
            print("── 露顶式闸门门顶（4.2.19）门顶 >= 最高挡水位 %.2f + 0.30 = %.2f"
                  % (zw_imp, need_gate))
            print("   （门顶为闸门高度要求，与闸顶高程并列，不并入其取大值）")
            print()

    # ---- 汇总 ----
    if not reqs:
        print("没有可汇总的闸顶高程约束（仅有旁证条目）。")
        if side_checks:
            for name, v, ref in side_checks:
                print("   %s >= %.2f（%s）" % (name, v, ref))
        return 0

    best = max(reqs, key=lambda r: r[1])
    print("── 综合建议闸顶高程")
    for name, v, ref in reqs:
        print("   %-22s %.2f m（%s）" % (name, v, ref))
    print("   ── 控制项 = %s，建议闸顶高程 >= %.2f m" % (best[0], best[1]))
    print("   " + "==>> " + "建议值 = %.2f m" % best[1])
    print()

    if args.reported is not None:
        ok = args.reported + 1e-9 >= best[1]
        print("── 复核报告取值")
        print("   报告闸顶高程 = %.2f m，要求 >= %.2f m" % (args.reported, best[1]))
        if ok:
            print("   ==>> 满足（余量 %.2f m）" % (args.reported - best[1]))
            return 0
        else:
            print("   ==>> 不满足：偏低 %.2f m" % (best[1] - args.reported))
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
