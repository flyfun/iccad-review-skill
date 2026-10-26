#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝坡抗滑稳定复核器 —— 按 SL 274-2001 第 8.3 节与附录 D（含强条 8.3.10/8.3.11/8.3.12）。

【判据来源（全部实测自 SL 274-2001 原文）】
    8.3.9   方法选型：均质坝、厚斜墙坝、厚心墙坝宜用简化毕肖普法；
            有软弱夹层、薄斜墙、薄心墙坝可用摩根斯顿—普赖斯法；
            非均质坝体/坝基须考虑安全系数多极值特性，取最小安全系数。
    8.3.1   必须计算的四种工况：① 施工期上下游坝坡；② 稳定渗流期上下游坝坡；
            ③ 水库水位降落期上游坝坡；④ 正常运用遇地震上下游坝坡。
    8.3.10  允许值查「表 8.3.10」                        （★强制性条文）
    8.3.11  瑞典圆弧法（不计条块间作用力）：1 级坝正常运用最小 1.30；
            其他情况 = 表 8.3.10 数值 ×0.92（减小 8%）      （★强制性条文）
    8.3.12  滑楔法：作用力平行坡面 → 按表 8.3.10；作用力水平 → 按 8.3.11（×0.92）（★强条）
    8.3.5   抗剪强度指标应采用三轴仪测定；3 级以下中坝可用直剪慢剪；
            渗透系数 <1e-7 cm/s 或压缩系数 <0.2 MPa⁻¹ 的土可用直剪快剪或固结快剪。
    表D.1.1 抗剪强度指标的测定和应用（按控制稳定时期 + 应力法 + 土类查试验方法）

【表 8.3.10 坝坡抗滑稳定最小安全系数 —— 实测自原文】
    运用条件          1级    2级    3级   4、5级
    正常运用条件      1.50   1.35   1.30  1.25
    非常运用条件 I    1.30   1.25   1.20  1.15
    非常运用条件 II   1.20   1.15   1.15  1.10
   （运用条件划分见 SL 274-2001 第 1.0.5 条；非常运用条件I含施工期、校核洪水位、水位非常降落；
     非常运用条件II含正常运用遇地震等）

【⚠️ 本脚本不做的两件事（别高估）】
    ① 不替你算稳定安全系数：条分法（简化毕肖普/瑞典圆弧/摩根斯顿—普赖斯）需完整坝体
       断面、分条、土层参数与孔隙压力，属专业软件的活。本脚本只做**允许值查表 + 判定**。
    ② 不替你判"滑弧找得对不对"：安全系数多极值特性要求在不同土层比较滑面，
       仍须专业判断。本脚本只保证**允许值这一侧**不出错。

【退出码】0 = 满足；1 = 不满足；2 = 参数不足（只出允许值，无计算值可比）
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ===== 表 8.3.10 坝坡抗滑稳定最小安全系数（实测自原文）=====
LIMIT = {
    "normal":    {1: 1.50, 2: 1.35, 3: 1.30, 4: 1.25, 5: 1.25},
    "abnormal1": {1: 1.30, 2: 1.25, 3: 1.20, 4: 1.15, 5: 1.15},
    "abnormal2": {1: 1.20, 2: 1.15, 3: 1.15, 4: 1.10, 5: 1.10},
}
CASE_CN = {"normal": "正常运用条件", "abnormal1": "非常运用条件 I", "abnormal2": "非常运用条件 II"}

# ===== 表 D.1.1 抗剪强度指标的测定和应用（结构化，实测自原文）=====
# key = (阶段, 应力法) → 规范要求的（仪器/试验方法/强度指标）
TEST_TABLE = {
    ("construction", "effective", "cohesionless"): "直剪仪 慢剪(S) 或 三轴仪 固结排水剪(CD) → c′、φ′",
    ("construction", "effective", "cohesive_unsat"): "直剪仪 慢剪(S) 或 三轴仪 不排水剪测孔隙压力(UU)",
    ("construction", "effective", "cohesive_sat"): "直剪仪 慢剪(S) 或 三轴仪 固结不排水剪测孔隙压力(CU)",
    ("construction", "total", "cohesive_lowk"): "直剪仪 快剪(Q) → Cu、φu",
    ("construction", "total", "cohesive_any"): "三轴仪 不排水剪(UU)",
    ("steady", "effective", "cohesionless"): "直剪仪 慢剪(S) 或 三轴仪 固结排水剪(CD) → c′、φ′",
    ("steady", "effective", "cohesive"): "直剪仪 慢剪(S) 或 三轴仪 固结不排水剪测孔隙压力(CU)/固结排水剪(CD)",
    ("drawdown", "total", "cohesive_lowk"): "直剪仪 固结快剪(R) → Ccu、φcu",
    ("drawdown", "total", "cohesive_any"): "三轴仪 固结不排水剪(CU)",
}
STAGE_CN = {"construction": "施工期", "steady": "稳定渗流期和水库水位降落期", "drawdown": "水库水位降落期"}


def norm_level(x):
    return 4 if x >= 4 else x


def do_allow(args):
    """模式一：查允许值并判定报告的稳定安全系数。"""
    lv = norm_level(args.level)
    base = LIMIT[args.case][lv]
    method = args.method
    allowed = base
    note = ""

    if method == "swedish":
        # 8.3.11：不计条块间作用力的瑞典圆弧法
        if lv == 1 and args.case == "normal":
            allowed = 1.30
            note = "（8.3.11：1 级坝正常运用，最小 1.30）"
        else:
            allowed = round(base * 0.92, 4)
            note = "（8.3.11：非 1级坝正常运用，表值 ×0.92＝减小 8%）"
    elif method == "wedge-horizontal":
        # 8.3.12：滑楔法、作用力水平 → 按 8.3.11
        if lv == 1 and args.case == "normal":
            allowed = 1.30
        else:
            allowed = round(base * 0.92, 4)
        note = "（8.3.12：假定滑楔间作用力水平 → 按 8.3.11 取值）"
    elif method == "wedge-parallel":
        note = "（8.3.12：假定作用力平行坡面与滑底平均坡度 → 按表 8.3.10）"
    # bishop（简化毕肖普）→ 直接用表 8.3.10

    print("【坝坡抗滑稳定】SL 274-2001 第 8.3 节（含强制性条文 8.3.10 / 8.3.11 / 8.3.12）")
    print("  工程级别 = %d 级   运用条件 = %s（划分见 1.0.5）" % (args.level, CASE_CN[args.case]))
    print("  计算方法 = %s" % {
        "bishop": "简化毕肖普法（计及条块间作用力）",
        "swedish": "瑞典圆弧法（不计条块间作用力）",
        "wedge-parallel": "滑楔法（作用力平行坡面）",
        "wedge-horizontal": "滑楔法（作用力水平）",
    }[method])
    print("  ── 表 8.3.10 基准允许值 = %.2f" % base)
    print("  ── 本情形允许值 [K] = %.4f %s" % (allowed, note))

    if args.calc is None:
        print("\n（未给 --calc，仅出允许值；退出码 2）")
        return 2
    print("\n── 对比报告计算值")
    print("   报告 K = %.3f vs 允许值 [K] = %.4f" % (args.calc, allowed))
    if args.calc >= allowed - 1e-9:
        print("   ==>> 满足（余量 %.3f）" % (args.calc - allowed))
        return 0
    print("   ==>> 不满足（差 %.3f）—— 违反强制性条文 %s"
          % (allowed - args.calc, "8.3.11" if method in ("swedish", "wedge-horizontal") else "8.3.10"))
    return 1


def do_test(args):
    """模式二：查表 D.1.1，核对报告选用的抗剪强度试验方法是否规范。"""
    if args.stage == "steady":
        soc = "cohesionless" if args.soil == "cohesionless" else "cohesive"
    elif args.stage == "construction":
        if args.soil == "cohesionless":
            soc = "cohesionless"
        else:
            soc = "cohesive_sat" if args.sat_high else "cohesive_unsat"
        if args.stress == "total":
            soc = "cohesive_lowk" if args.low_k else "cohesive_any"
    else:  # drawdown
        soc = "cohesive_lowk" if args.low_k else "cohesive_any"

    print("【抗剪强度试验方法】SL 274-2001 表 D.1.1（附录 D）")
    print("  控制稳定时期 = %s" % STAGE_CN[args.stage])
    print("  强度计算方法 = %s" % ("有效应力法" if args.stress == "effective" else "总应力法"))
    print("  土类 = %s" % ("无粘性土" if args.soil == "cohesionless" else "粘性土"))
    key = (args.stage, args.stress, soc)
    req = TEST_TABLE.get(key)
    if req is None:
        print("   ⚠ 该组合在表 D.1.1 中无对应行，请回原文核对（可能组合不成立）")
        return 2
    print("  ── 规范要求的试验方法：" + req)
    print("\n  另注意 8.3.5：土的抗剪强度指标应采用**三轴仪**测定；3 级以下中坝可用直接慢剪；")
    print("           渗透系数 <1e-7 cm/s 或压缩系数 <0.2 MPa⁻¹ 的土，可用直接快剪或固结快剪测总强度指标。")
    print("  另注意 D.1.2：稳定渗流期用有效应力法；施工期和库水位降落期应**同时**用有效应力法和总应力法，")
    print("           并以**较小的安全系数**为准。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="坝坡抗滑稳定复核（SL 274-2001 第 8.3 节 / 附录 D）")
    ap.add_argument("--mode", choices=["allow", "test"], default="allow",
                    help="allow=查允许值并判定（默认）；test=查表 D.1.1 试验方法")
    ap.add_argument("--level", type=int, default=2, help="工程级别 1/2/3/4/5")
    ap.add_argument("--case", choices=["normal", "abnormal1", "abnormal2"], default="normal",
                    help="运用条件：normal / abnormal1（施工、校核洪水、水位非常降落）/ abnormal2（地震等）")
    ap.add_argument("--method", choices=["bishop", "swedish", "wedge-parallel", "wedge-horizontal"],
                    default="bishop", help="计算方法（默认简化毕肖普）")
    ap.add_argument("--calc", type=float, default=None, help="报告计算的稳定安全系数 K")
    # test 模式参数
    ap.add_argument("--stage", choices=["construction", "steady", "drawdown"], default="steady")
    ap.add_argument("--stress", choices=["effective", "total"], default="effective")
    ap.add_argument("--soil", choices=["cohesionless", "cohesive"], default="cohesive")
    ap.add_argument("--sat-high", action="store_true", help="粘性土饱和度 > 80%%")
    ap.add_argument("--low-k", action="store_true", help="渗透系数 < 1e-7 cm/s")
    args = ap.parse_args()

    if args.mode == "test":
        sys.exit(do_test(args))
    sys.exit(do_allow(args))


if __name__ == "__main__":
    main()
