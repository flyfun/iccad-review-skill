#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""坝顶高程 / 坝顶超高 / 防渗体顶部高程 复核器 —— SL 274-2001 第 5.3 节（★强条 5.3.1）＋ 5.4.4（防浪墙墙高）＋ 5.5（防渗体）。

【判据来源（全部实测自 SL 274-2001 原文 docx，2026-10-11 核对）】
    ── 一、坝顶（第 5.3 / 5.4 节）──
    5.3.1  坝顶超高  y = R + e + A                      （★强制性条文）
            A 查「表 5.3.1 安全加高 A 值」
    5.3.2  地震区安全加高尚应增加地震沉降和地震壅浪高度
    5.3.3  坝顶高程 = 水库静水位 + 坝顶超高，按四种运用条件计算，取最大值：
             ① 设计洪水位 + 正常运用条件的坝顶超高
             ② 正常蓄水位 + 正常运用条件的坝顶超高
             ③ 校核洪水位 + 非常运用条件的坝顶超高
             ④ 正常蓄水位 + 非常运用条件的坝顶超高，再按 5.3.2 加地震安全加高
    5.3.4  设防浪墙时，坝顶超高可改为对防浪墙顶的要求；但此时
             正常运用条件下，坝顶应高出静水位 0.5m（静水位含正常蓄水位与设计洪水位）；
             非常运用条件下，坝顶应不低于静水位。
    5.3.5  设计风速取值（正常运用 1/2 级坝取多年平均年最大风速 1.5~2.0 倍；3/4/5 级 1.5 倍；
           非常运用取多年平均年最大风速）—— 反映到 R、e 的取值上。
    5.3.6  预留沉降超高不计入坝的计算高度。
    5.4.4  坝顶上游侧宜设防浪墙，**墙顶应高于坝顶 1.00~1.20m**（原文实测）。
           —— 由它派生出 坝顶 = 防浪墙顶 − 墙高（墙高 h ∈ 1.00~1.20 m）。

    ── 二、防渗体顶部高程（第 5.5 节；5.5.3 为★强制性条文）──
    5.5.3  土质防渗体顶部在正常蓄水位或设计洪水位以上的超高，应按表 5.5.3 取值；
           非常运用条件下，防渗体顶部不应低于非常运用条件的静水位；并应核算风浪爬高高度的影响。
           当防渗体顶部设有防浪墙时，防渗体顶部高程可不受上述限制，但不得低于正常运用的静水位。
           防渗体顶部应预留竣工后沉降超高。
    5.5.4  土质防渗体顶部和土质斜墙上游应设保护层。保护层厚度（包括上游护坡垫层）
           应不小于该地区的冻结和干燥深度，还应满足施工机械的需要。
           —— 派生判据：上游保护层厚度 = 坝顶高程 − 防渗体顶高程 ≥ 冻结/干燥深度。

【两种坝顶方案（本脚本分别复核）】
    方案 A · 无防浪墙（上游坝顶不设墙）：
        所需坝顶高程 T_A = max(四工况 静水位 + 超高 y)。
    方案 B · 有防浪墙（上游坝顶设防浪墙，5.4.4）：
        所需防浪墙顶 T_B = max(四工况 静水位 + 超高 y)；
        由墙顶反推坝顶   = T_B − h            （h = 墙顶高出坝顶值，默认 1.20，规定 1.00~1.20）
        且坝顶还须满足 5.3.4 静水位限值：
            正常运用：坝顶 ≥ max(正常蓄水位, 设计洪水位) + 0.5
            非常运用：坝顶 ≥ 校核洪水位
        取三者最大 → 所需坝顶 T_B_dam。
    —— 报告选哪种方案由 `--parapet` 指定（给了 `--wall-crest` 亦自动按有防浪墙处理）。

【两种防渗体顶部方案（5.5.3；给了 --core-type 时复核）】
    方案 C-A · 无防浪墙：
        正常运用  防渗体顶 ≥ max(正常蓄水位, 设计洪水位) + hc   （hc 查表 5.5.3）
        非常运用  防渗体顶 ≥ 校核洪水位
        取大值。
    方案 C-B · 有防浪墙（5.5.3 第 3 段）：
        防渗体顶不受超高限制，但 ≥ max(正常蓄水位, 设计洪水位)。
    —— 与坝顶方案同用 `--parapet` 判定；给了 `--core-top` 则与报告值复核。
    另：预留竣工后沉降超高（5.5.3 第 4 段）—— 竣工填筑高程 = 运行期所需 + 沉降量；
        保护层校核（5.5.4）—— 坝顶高程 − 防渗体顶高程 ≥ 冻结/干燥深度。

【表 5.3.1 安全加高 A 值（m）—— 实测自原文】
    运用情况    1级    2级    3级   4、5级
    设计        1.50   1.00   0.70  0.50
    校核 山区丘陵区 0.70 0.50  0.40  0.30
    校核 平原滨海区 1.00 0.70  0.50  0.30

【表 5.5.3 正常运用情况下防渗体顶部超高 hc（m）—— 实测自原文】
    防渗体结构形式   超高
    斜墙            0.80～0.60
    心墙            0.60～0.30
    （为区间值，设计在区间内选取；本脚本判定取下限，另打印上限供参考）

【⚠️ 公式核对提醒】
    R（波浪爬高）与 e（风壅高度）的**计算式在原文中为嵌入图片**，机器提取不到文字。
    本脚本**不替你把 R、e 算出来**——请你从报告或按附录 A 手工提供 R、e；
    脚本负责 5.3.3 的四工况取大值、5.4.4 的墙高推算、5.5.3/5.5.4 的防渗体查表判定
    （这部分限值实测自原文，可靠）。

【退出码】0 = 满足；1 = 不满足；2 = 参数不足（未给任何报告值，只出建议值）
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ===== 表 5.3.1 安全加高 A 值（m），实测自 SL 274-2001 原文 =====
A_DESIGN = {1: 1.50, 2: 1.00, 3: 0.70, 4: 0.50, 5: 0.50}          # 设计（正常运用条件）
A_CHECK_MOUNTAIN = {1: 0.70, 2: 0.50, 3: 0.40, 4: 0.30, 5: 0.30}   # 校核（非常运用）· 山区、丘陵区
A_CHECK_PLAIN = {1: 1.00, 2: 0.70, 3: 0.50, 4: 0.30, 5: 0.30}      # 校核（非常运用）· 平原、滨海区

# ===== 表 5.5.3 防渗体顶部超高（m），实测自原文：斜墙 0.80~0.60，心墙 0.60~0.30 =====
CORE_FREEBOARD = {"inclined": (0.60, 0.80), "central": (0.30, 0.60)}   # 斜墙 / 心墙 (下限, 上限)
CORE_NAME = {"inclined": "斜墙", "central": "心墙"}

# ===== 5.4.4 防浪墙墙高（墙顶高出坝顶）规定区间，m，实测自原文 =====
WALL_H_MIN, WALL_H_MAX = 1.00, 1.20


def norm_level(x):
    """级别归一化：4、5 级同值处理（表里 4、5 级共用一列）。"""
    return 4 if x >= 4 else x


def main():
    ap = argparse.ArgumentParser(description="坝顶高程/坝顶超高（5.3/5.4）＋ 防渗体顶部高程（5.5）复核，SL 274-2001")
    ap.add_argument("--level", type=int, required=True, help="工程级别 1/2/3/4/5")
    ap.add_argument("--region", choices=["mountain", "plain"], default="mountain",
                    help="校核洪水位安全加高分区：mountain=山区丘陵区（默认）/ plain=平原滨海区")
    ap.add_argument("--zw-normal", type=float, default=None, help="正常蓄水位 m")
    ap.add_argument("--zw-design", type=float, default=None, help="设计洪水位 m")
    ap.add_argument("--zw-check", type=float, default=None, help="校核洪水位 m")
    ap.add_argument("--R", type=float, default=0.0, help="正常运用条件的波浪爬高 R，m")
    ap.add_argument("--e", type=float, default=0.0, help="正常运用条件的风壅水面高度 e，m")
    ap.add_argument("--R-abnormal", type=float, default=None, help="非常运用条件的 R，m（默认取 --R）")
    ap.add_argument("--e-abnormal", type=float, default=None, help="非常运用条件的 e，m（默认取 --e）")
    ap.add_argument("--seismic", type=float, default=0.0, help="地震安全加高（含地震沉降+壅浪），m")
    ap.add_argument("--parapet", action="store_true",
                    help="报告采用『有防浪墙』方案（坝顶方案 B / 防渗体方案 C-B）；不给则按『无防浪墙』复核")
    ap.add_argument("--wall-height", type=float, default=WALL_H_MAX,
                    help="防浪墙顶高出坝顶的高度 h，m（SL 274-2001 5.4.4 规定 1.00~1.20，默认 1.20）")
    ap.add_argument("--dam-crest", type=float, default=None, help="报告坝顶高程 m（坝顶两方案 + 保护层校核都用它）")
    ap.add_argument("--wall-crest", type=float, default=None,
                    help="报告防浪墙顶高程 m（有防浪墙方案 B 用；给了它自动按方案 B 处理）")
    # ── 防渗体（5.5）──
    ap.add_argument("--core-type", choices=["inclined", "central"], default=None,
                    help="土质防渗体型式：inclined=斜墙 / central=心墙（触发 5.5.3 防渗体顶部高程复核）")
    ap.add_argument("--core-top", type=float, default=None, help="报告防渗体顶部高程 m（5.5.3 判定用；指竣工填筑/设计高程）")
    ap.add_argument("--core-hc", type=float, default=None,
                    help="防渗体顶部超高 hc，m（默认取表 5.5.3 下限；仅当报告明确选定区间内某值时用）")
    ap.add_argument("--dam-height", type=float, default=None, help="坝高 m（用 --settlement-ratio 算沉降超高时必给）")
    ap.add_argument("--settlement", type=float, default=None, help="防渗体预留竣工后沉降超高 Δhc（绝对值），m")
    ap.add_argument("--settlement-ratio", type=float, default=None,
                    help="防渗体预留沉降超高占坝高比例（如 0.0045 表示 0.45%%），配 --dam-height 用")
    ap.add_argument("--freeze-depth", type=float, default=None,
                    help="上游保护层厚度下限＝冻结/干燥深度，m（5.5.4 校核：坝顶−防渗体顶 ≥ 该值）")
    ap.add_argument("--reported", type=float, default=None,
                    help="[兼容旧参数] 报告顶高程：等同 --dam-crest（若未给 --dam-crest）")
    args = ap.parse_args()

    lv = norm_level(args.level)
    if args.level not in (1, 2, 3, 4, 5):
        raise SystemExit("级别须为 1~5")
    A_des = A_DESIGN[lv]
    A_chk = (A_CHECK_MOUNTAIN if args.region == "mountain" else A_CHECK_PLAIN)[lv]
    R_ab = args.R if args.R_abnormal is None else args.R_abnormal
    e_ab = args.e if args.e_abnormal is None else args.e_abnormal

    # 报告坝顶：--dam-crest 优先，其次兼容参数 --reported
    dam_crest = args.dam_crest if args.dam_crest is not None else args.reported
    # 方案判定：显式 --parapet，或给了 --wall-crest，即按有防浪墙（方案 B / C-B）
    use_parapet = args.parapet or (args.wall_crest is not None)

    h = args.wall_height
    h_warn = "" if (WALL_H_MIN - 1e-9) <= h <= (WALL_H_MAX + 1e-9) else \
        "   ⚠ 墙高 h=%.3f 不在 5.4.4 规定区间 [%.2f, %.2f] 内" % (h, WALL_H_MIN, WALL_H_MAX)

    print("【坝顶高程 / 坝顶超高 / 防渗体顶部高程 复核】SL 274-2001 第 5.3 / 5.4 / 5.5 节")
    print("  工程级别 = %d 级   校核分区 = %s"
          % (args.level, "山区、丘陵区" if args.region == "mountain" else "平原、滨海区"))
    print("  安全加高：设计(正常运用) A = %.2f m；校核(非常运用) A = %.2f m（表 5.3.1）" % (A_des, A_chk))
    print("  波浪爬高 R = %.3f / 风壅高度 e = %.3f（正常运用）；R = %.3f / e = %.3f（非常运用）"
          % (args.R, args.e, R_ab, e_ab))
    if not (args.zw_normal is not None or args.zw_design is not None or args.zw_check is not None):
        raise SystemExit("至少给一个特征水位（--zw-normal / --zw-design / --zw-check）")

    # —— 5.3.3 四种运用条件 ——
    cases = []
    if args.zw_design is not None:
        cases.append(("① 设计洪水位＋正常运用", args.zw_design, args.R + args.e + A_des))
    if args.zw_normal is not None:
        cases.append(("② 正常蓄水位＋正常运用", args.zw_normal, args.R + args.e + A_des))
    if args.zw_check is not None:
        cases.append(("③ 校核洪水位＋非常运用", args.zw_check, R_ab + e_ab + A_chk))
    if args.zw_normal is not None:
        cases.append(("④ 正常蓄水位＋非常运用＋地震", args.zw_normal, R_ab + e_ab + A_chk + args.seismic))

    print("\n── 5.3.3 四种运用条件（分别算「静水位 ＋ 坝顶超高 y」，取最大值）")
    best = None
    for name, zw, y in cases:
        crest = zw + y
        if best is None or crest > best[2]:
            best = (name, y, crest, zw)
        # 注意：用"正常运用"（而非"正常"）判定 —— 工况④名含"正常蓄水位"但不是正常运用
        is_normal = "正常运用" in name
        parts = "%.3f+%.3f+%.3f" % (
            args.R if is_normal else R_ab,
            args.e if is_normal else e_ab,
            A_des if is_normal else A_chk)
        if args.seismic and "地震" in name:
            parts += "+%.3f(地震)" % args.seismic
        print("   %-26s 水位 %8.2f ＋ 超高 %.3f(%s) = %8.3f m"
              % (name, zw, y, parts, crest))

    ctrl_name, ctrl_y, T, T_zw = best
    print("   控制工况 = %s → 所需顶高程 T = %.3f m（＝水位 %.2f ＋ 超高 %.3f）"
          % (ctrl_name, T, T_zw, ctrl_y))

    # ── 方案 A：无防浪墙 ──
    need_dam_A = T
    print("\n══ 方案 A · 无防浪墙 ═══════════════════════════════════════════")
    print("   所需坝顶高程 = T = %.3f m" % need_dam_A)
    print("   说明：无防浪墙时，坝顶超高的全部由坝顶承担。")

    # ── 方案 B：有防浪墙（5.4.4）──
    need_wall_B = T
    need_dam_B_wall = T - h
    normal_static = max([z for z in (args.zw_normal, args.zw_design) if z is not None] or [None])
    print("\n══ 方案 B · 有防浪墙（SL 274-2001 5.4.4：墙顶应高于坝顶 1.00~1.20 m）════")
    print("   所需防浪墙顶高程 = T = %.3f m" % need_wall_B)
    print("   由墙顶反推坝顶     = 墙顶 − h = %.3f − %.3f = %.3f m" % (T, h, need_dam_B_wall))
    print("   若 h 取 %.2f → 坝顶 %.3f m（墙矮、坝顶高）" % (WALL_H_MIN, T - WALL_H_MIN))
    if h_warn:
        print(h_warn)

    print("   5.3.4 附加校核（设防浪墙时，坝顶不得低于静水位）：")
    need_dam_B = need_dam_B_wall
    if normal_static is not None:
        req = normal_static + 0.5
        need_dam_B = max(need_dam_B, req)
        flag = "✓" if need_dam_B_wall >= req - 1e-9 else "✗（坝顶由 5.3.4 控制）"
        print("     正常运用：坝顶需 ≥ max(正常蓄水位, 设计洪水位)%.2f ＋ 0.5 = %.3f  %s"
              % (normal_static, req, flag))
    if args.zw_check is not None:
        req = args.zw_check
        need_dam_B = max(need_dam_B, req)
        flag = "✓" if need_dam_B_wall >= req - 1e-9 else "✗（坝顶由 5.3.4 控制）"
        print("     非常运用：坝顶需 ≥ 校核洪水位 = %.3f  %s" % (req, flag))
    print("   → 所需坝顶高程 = max(墙顶−h, 5.3.4 限值) = %.3f m" % need_dam_B)

    # ════════ 5.5.3 / 5.5.4 防渗体顶部高程 ════════
    code = 0
    core_need_fill = None          # 含预留沉降后的竣工填筑高程（报告比对基准）
    if args.core_type:
        lo, hi = CORE_FREEBOARD[args.core_type]
        nm = CORE_NAME[args.core_type]
        hc_use = args.core_hc if args.core_hc is not None else lo
        base = max([z for z in (args.zw_normal, args.zw_design) if z is not None] or [None])

        print("\n══ 防渗体顶部高程（★强条 5.5.3；保护层 5.5.4）══════════════════════")
        print("   防渗体型式 = %s（表 5.5.3 正常运用超高 hc = %.2f~%.2f m；本脚本判定取 %.2f）"
              % (nm, hi, lo, hc_use))
        if args.core_hc is not None and not (lo - 1e-9) <= args.core_hc <= (hi + 1e-9):
            print("   ⚠ 指定的 hc=%.3f 不在表 5.5.3 区间 [%.2f, %.2f] 内" % (args.core_hc, lo, hi))

        # —— 方案 C-A · 无防浪墙 ——
        need_A = None
        if base is not None:
            need_A = base + hc_use
            print("   ── 方案 C-A · 无防浪墙")
            print("      正常运用：max(正常蓄水位, 设计洪水位) = %.3f ＋ hc %.2f = %.3f m"
                  "（若取上限 hc=%.2f 则 %.3f）" % (base, hc_use, need_A, hi, base + hi))
        if args.zw_check is not None:
            print("      非常运用：≥ 校核洪水位 = %.3f m" % args.zw_check)
            need_A = args.zw_check if need_A is None else max(need_A, args.zw_check)
        if need_A is not None:
            print("      → 防渗体顶需 ≥ %.3f m" % need_A)

        # —— 方案 C-B · 有防浪墙 ——
        need_B = base      # max(正常蓄水位, 设计洪水位)
        print("   ── 方案 C-B · 有防浪墙（5.5.3 第 3 段：不受超高限制，但 ≥ 正常运用静水位）")
        if need_B is not None:
            print("      → 防渗体顶需 ≥ max(正常蓄水位, 设计洪水位) = %.3f m" % need_B)
        else:
            print("      （未给正常蓄水位/设计洪水位，无法判定）")

        need_core = need_B if use_parapet else need_A
        print("   ── 采用方案 = %s（%s）"
              % ("C-B · 有防浪墙" if use_parapet else "C-A · 无防浪墙",
                 "运行期所需最低 = %.3f m" % need_core if need_core is not None else "无法判定"))
        print("   注：按 5.5.3，尚应核算**风浪爬高**影响（本脚本不代算，请核对 R 是否已计入 hc）。")

        # —— 预留竣工后沉降超高（5.5.3 第 4 段）——
        settle = args.settlement
        if settle is None and args.settlement_ratio is not None and args.dam_height is not None:
            settle = args.settlement_ratio * args.dam_height
            print("   ── 预留竣工后沉降超高 Δhc = %.4f × %.2f m（坝高） = %.3f m"
                  % (args.settlement_ratio, args.dam_height, settle))
        elif settle is not None:
            print("   ── 预留竣工后沉降超高 Δhc = %.3f m" % settle)
        if settle is None:
            settle = 0.0
            print("   ── 未给预留竣工后沉降超高（--settlement / --settlement-ratio）：按 0 计，"
                  "实际应补（5.5.3）")
        if need_core is not None:
            core_need_fill = need_core + settle
            print("   ── 竣工填筑高程需 ≥ 运行期所需 %.3f ＋ 沉降 %.3f = %.3f m"
                  % (need_core, settle, core_need_fill))

        # —— 报告防渗体顶复核 ——
        if args.core_top is not None and core_need_fill is not None:
            okc = args.core_top >= core_need_fill - 1e-9
            print("   ── 报告防渗体顶 = %.3f m vs 需 ≥ %.3f m → %s（余量 %+.3f m）"
                  % (args.core_top, core_need_fill, "满足" if okc else "不满足",
                     args.core_top - core_need_fill))
            if not okc:
                print("      ==>> 违反强制性条文 5.5.3（防渗体顶部超高不足）")
                code = 1
        elif args.core_top is not None:
            print("   ── 报告防渗体顶 = %.3f m（未给特征水位，无法判定）" % args.core_top)

        # —— 保护层校核（5.5.4）——
        if args.freeze_depth is not None and args.core_top is not None and dam_crest is not None:
            thick = dam_crest - args.core_top
            okf = thick >= args.freeze_depth - 1e-9
            print("   ── 保护层校核（5.5.4）：坝顶 %.3f − 防渗体顶 %.3f = %.3f m vs 冻结/干燥深度 %.3f m → %s"
                  % (dam_crest, args.core_top, thick, args.freeze_depth, "满足" if okf else "不满足"))
            if not okf:
                print("      ==>> 违反 5.5.4（上游保护层厚度小于冻结/干燥深度）")
                code = 1
        elif args.freeze_depth is not None:
            print("   ── 保护层校核（5.5.4）：需同时给 --core-top 与 --dam-crest，暂无法判定")

    # —— 复核报告取值（坝顶）——
    print("\n── 复核报告取值（采用方案：%s）" % ("B · 有防浪墙" if use_parapet else "A · 无防浪墙"))
    have_any = False

    if use_parapet:
        if args.wall_crest is not None:
            have_any = True
            ok = args.wall_crest >= need_wall_B - 1e-9
            print("   防浪墙顶：报告 %.3f m vs 需 ≥ %.3f m → %s（余量 %+.3f m）"
                  % (args.wall_crest, need_wall_B, "满足" if ok else "不满足", args.wall_crest - need_wall_B))
            if not ok:
                print("     ==>> 违反 5.3.1 + 5.3.3（防浪墙顶超高不足）")
                code = 1
        if dam_crest is not None:
            have_any = True
            ok = dam_crest >= need_dam_B - 1e-9
            print("   坝顶　　：报告 %.3f m vs 需 ≥ %.3f m → %s（余量 %+.3f m）"
                  % (dam_crest, need_dam_B, "满足" if ok else "不满足", dam_crest - need_dam_B))
            if not ok:
                print("     ==>> 违反 5.3.4（设防浪墙时坝顶低于静水位要求）")
                code = 1
        if args.wall_crest is not None and dam_crest is not None:
            dh = args.wall_crest - dam_crest
            okh = (WALL_H_MIN - 1e-9) <= dh <= (WALL_H_MAX + 1e-9)
            print("   墙高　　：墙顶−坝顶 = %.3f − %.3f = %.3f m vs 5.4.4 规定 [%.2f, %.2f] → %s"
                  % (args.wall_crest, dam_crest, dh, WALL_H_MIN, WALL_H_MAX, "符合" if okh else "不符合"))
            if not okh:
                print("     ==>> 不符合 5.4.4（墙顶应高于坝顶 1.00~1.20 m）")
                code = 1
    else:
        if dam_crest is not None:
            have_any = True
            ok = dam_crest >= need_dam_A - 1e-9
            print("   坝顶　　：报告 %.3f m vs 需 ≥ %.3f m → %s（余量 %+.3f m）"
                  % (dam_crest, need_dam_A, "满足" if ok else "不满足", dam_crest - need_dam_A))
            if not ok:
                print("     ==>> 违反强制性条文 5.3.1（坝顶超高不足）")
                code = 1

    if not have_any and core_need_fill is None and args.core_top is None:
        print("\n（未给任何报告值 --dam-crest / --wall-crest / --core-top，仅出建议值；退出码 2）")
        sys.exit(2 if code == 0 else code)
    sys.exit(code)


if __name__ == "__main__":
    main()
