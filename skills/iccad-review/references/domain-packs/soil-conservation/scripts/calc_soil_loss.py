#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""土壤流失量预测复核器 —— 依 GB 50433-2018《生产建设项目水土保持技术标准》4.5.3 / 4.5.6。

【干什么】
    把报告"水土流失预测"章（块 5）的关键中间量自己过一遍：
      ① 分单元土壤流失量  W = Σ Fᵢ · Mᵢ · Tᵢ      （4.5.3）
           Fᵢ 第 i 单元预测面积(km²)  Mᵢ 扰动后土壤侵蚀模数〔t/(km²·a)〕  Tᵢ 预测时段长(a)
      ② 各单元"新增"土壤流失量 = 扰动后 − 原地貌；**恢复到原地貌水平以下时不再计**（4.5.3）
      ③ 自然恢复期长度校验（4.5.6）：湿润区 2 年 / 半湿润区 3 年 / 干旱半干旱区 5 年
      ④ 土壤流失控制比 = 容许土壤流失量 ÷ 治理后侵蚀模数（GB/T 50434 2.0.2），对照限值判达标
      ⑤ 可选：按 SL 190-2007 表 4.1.2-1 给一个侵蚀模数判强度级别（--grade）

【限值 / 公式来源】
    GB 50433-2018 4.5.3（W=ΣF·M·T）、4.5.6（自然恢复期长度）——实测自本机原始文件；
    GB/T 50434-2018 2.0.2（土壤流失控制比定义）；SL 190-2007 表 4.1.2-1（强度分级）。

【用法】
    # 分单元预测（单元写法：名称:面积hm²:原地貌M:扰动后M:时段a[:阶段]）
    python calc_soil_loss.py --region 半湿润 \
      --unit "施工期·主体工程区:2.50:800:6500:1.5:施工期" \
      --unit "自然恢复期·主体工程区:2.50:800:2500:3:自然恢复期"

    # 从 CSV 读单元（列：名称,面积hm²,原地貌M,扰动后M,时段a,阶段）
    python calc_soil_loss.py --region 湿润 --units-file units.csv

    # 只核控制比
    python calc_soil_loss.py --allowable 500 --post-modulus 420 --control-limit 0.85

    # 判侵蚀强度级别（SL 190 表 4.1.2-1，容许值用于划分微度/轻度界线）
    python calc_soil_loss.py --grade 3200 --grade-allowable 500

【退出码】
    0 = 预测完成且（若给控制比）达标；1 = 控制比不达标 / 恢复期长度不符；2 = 参数错误。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 自然恢复期长度（GB 50433-2018 4.5.6）：区域 → 年数
RECOVERY_YEARS = {"湿润": 2, "半湿润": 3, "干旱半干旱": 5}

# SL 190-2007 表 4.1.2-1 水力侵蚀强度分级（容许值以上为轻度，其后为固定分界）
GRADE_BOUNDS = [(2500, "轻度"), (5000, "中度"), (8000, "强烈"),
                (15000, "极强烈")]


def parse_unit(spec):
    """'名称:面积hm²:原地貌M:扰动后M:时段a[:阶段]' → dict"""
    parts = spec.split(":")
    if len(parts) < 5:
        raise ValueError("单元格式应为 名称:面积hm²:原地貌M:扰动后M:时段a[:阶段] —— %r" % spec)
    name = parts[0].strip()
    try:
        area = float(parts[1])
        m_orig = float(parts[2])
        m_dist = float(parts[3])
        years = float(parts[4])
    except ValueError as e:
        raise ValueError("单元 %r 数值非法：%s" % (spec, e))
    stage = parts[5].strip() if len(parts) >= 6 and parts[5].strip() else ""
    return {"name": name, "area": area, "m_orig": m_orig, "m_dist": m_dist,
            "years": years, "stage": stage}


def load_units_file(path):
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cells = [c.strip() for c in line.replace("\t", ",").split(",")]
            if len(cells) < 5:
                raise ValueError("CSV 第 %d 行列数不足（需 名称,面积hm²,原地貌M,扰动后M,时段a[,阶段]）" % ln)
            if cells[1].lower() in ("面积", "area") or cells[0] in ("名称", "name"):
                continue  # 表头
            stage = cells[5] if len(cells) >= 6 else ""
            out.append({"name": cells[0], "area": float(cells[1]), "m_orig": float(cells[2]),
                        "m_dist": float(cells[3]), "years": float(cells[4]), "stage": stage})
    return out


def grade_of(modulus, allowable):
    """按 SL 190 表 4.1.2-1 判强度：容许值以上依次 轻度→中度→强烈→极强烈→剧烈。"""
    if modulus < allowable:
        return "微度"
    for bound, name in GRADE_BOUNDS:
        if modulus < bound:
            return name
    return "剧烈"


def main():
    ap = argparse.ArgumentParser(description="土壤流失量预测复核（GB 50433-2018 4.5.3 / 4.5.6）")
    ap.add_argument("--region", choices=list(RECOVERY_YEARS.keys()), help="区域（用于自然恢复期长度校验）")
    ap.add_argument("--recovery-len", type=float, help="报告给定的自然恢复期长度（年），用于与规范比对")
    ap.add_argument("--unit", action="append", default=[], help="单元：名称:面积hm²:原地貌M:扰动后M:时段a[:阶段]（可重复）")
    ap.add_argument("--units-file", help="CSV 单元文件（名称,面积hm²,原地貌M,扰动后M,时段a[,阶段]）")
    ap.add_argument("--allowable", type=float, help="容许土壤流失量〔t/(km²·a)〕（核控制比用）")
    ap.add_argument("--post-modulus", type=float, help="治理后侵蚀模数〔t/(km²·a)〕（核控制比用）")
    ap.add_argument("--control-limit", type=float, help="土壤流失控制比限值（如 0.85），用于判达标")
    ap.add_argument("--grade", type=float, help="给一个侵蚀模数判强度级别（SL 190 表 4.1.2-1）")
    ap.add_argument("--grade-allowable", type=float, default=500.0, help="判级时用于划分微度/轻度的容许值（默认 500）")
    args = ap.parse_args()

    rc = 0
    did = False

    # ① 判级（可选）
    if args.grade is not None:
        did = True
        g = grade_of(args.grade, args.grade_allowable)
        print("== 侵蚀强度判级（SL 190-2007 表 4.1.2-1）==")
        print("   侵蚀模数 %.0f t/(km²·a)（容许值 %.0f 划分微度/轻度）→ 【%s】"
              % (args.grade, args.grade_allowable, g))
        print()

    # ② 分单元预测
    units = []
    try:
        for s in args.unit:
            units.append(parse_unit(s))
        if args.units_file:
            units.extend(load_units_file(args.units_file))
    except (ValueError, OSError) as e:
        print("参数错误：%s" % e)
        return 2

    if units:
        did = True
        print("== 土壤流失量预测（GB 50433-2018 4.5.3：W = Σ F·M·T）==")
        tot_w = 0.0
        tot_new = 0.0
        print("   %-22s %10s %10s %10s %8s %12s %12s"
              % ("单元", "面积hm²", "M原", "M扰", "T(a)", "W(t)", "新增(t)"))
        for u in units:
            f_km2 = u["area"] / 100.0                      # hm² → km²
            w = f_km2 * u["m_dist"] * u["years"]
            new = f_km2 * (u["m_dist"] - u["m_orig"]) * u["years"]
            if new < 0:
                new = 0.0                                   # 恢复到原地貌以下不再计
            tot_w += w
            tot_new += new
            label = u["name"] + ("[%s]" % u["stage"] if u["stage"] else "")
            print("   %-22s %10.4f %10.0f %10.0f %8.2f %12.2f %12.2f"
                  % (label[:22], u["area"], u["m_orig"], u["m_dist"], u["years"], w, new))
        print("   " + "-" * 88)
        print("   合计：土壤流失量 W = %.2f t ；新增土壤流失量 = %.2f t" % (tot_w, tot_new))
        print("   注：F 由 hm² 换算 km²（÷100）；新增=扰动后−原地貌，负值按 0 计（4.5.3）。")
        print()

    # ③ 自然恢复期长度校验
    if args.region and args.recovery_len is not None:
        did = True
        std = RECOVERY_YEARS[args.region]
        ok = abs(args.recovery_len - std) < 1e-9
        print("== 自然恢复期长度校验（GB 50433-2018 4.5.6）==")
        print("   %s → 规范 %d 年 ；报告 %.1f 年 → %s"
              % (args.region, std, args.recovery_len, "一致" if ok else "★不一致"))
        if not ok:
            rc = 1
        print()

    # ④ 土壤流失控制比
    if args.allowable is not None and args.post_modulus is not None:
        did = True
        if args.post_modulus <= 0:
            print("参数错误：治理后侵蚀模数须为正数。")
            return 2
        ratio = args.allowable / args.post_modulus
        print("== 土壤流失控制比（GB/T 50434-2018 2.0.2）==")
        print("   控制比 = 容许流失量 %.0f ÷ 治理后侵蚀模数 %.0f = %.3f"
              % (args.allowable, args.post_modulus, ratio))
        if args.control_limit is not None:
            ok = ratio >= args.control_limit - 1e-9
            print("   限值 %.2f → %s" % (args.control_limit, "达标" if ok else "★不达标"))
            if not ok:
                rc = 1
        else:
            print("   （未给 --control-limit，仅出计算值；限值查 GB/T 50434 表 4.0.2）")
        print()

    if not did:
        ap.print_help()
        return 2

    print("依据：GB 50433-2018 4.5.3/4.5.6；GB/T 50434-2018 2.0.2；SL 190-2007 表 4.1.2-1。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
