#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""弃渣场级别与防护标准复核器 —— 依 GB 51018-2014《水土保持工程设计规范》第 5.7 节。

【干什么】
    给弃渣场"定级 → 定建筑物级别 → 定防洪标准 → 定抗滑安全系数"，全覆盖一算到底：
      ① 弃渣场级别     表 5.7.1（堆渣量 V、最大堆渣高度 H、危害程度；不一致时**就高不就低**）
      ② 拦挡工程级别   表 5.7.2（拦渣堤/拦渣坝/挡渣墙/排洪工程）
      ③ 防洪标准       表 5.7.3（山区丘陵 / 平原滨海；设计 + 校核）
      ④ 抗滑安全系数   表 5.7.4-1（毕肖普/摩根斯顿-普赖斯）、表 5.7.4-2（瑞典/改良圆弧）
      ⑤ 拦挡工程稳定   表 5.7.5-1（挡渣墙基底抗滑，土基/岩基）、5.7.5-2（土基抗倾覆）、5.7.5-3（拦渣堤抗滑）

【限值来源】
    GB 51018-2014 第 5.7 节，实测自本机原始 docx（非记忆）。

【用法】
    # 定级 + 出全套防护标准
    python calc_dregs.py --volume 300 --height 70 --region 山区丘陵
    # 已知危害程度（与堆渣量/高度取高）
    python calc_dregs.py --volume 300 --height 70 --region 山区丘陵 --hazard 较严重
    # 复核报告给的抗滑安全系数
    python calc_dregs.py --volume 300 --height 70 --region 山区丘陵 --method bishop --case normal --calc-k 1.28

    参数：--volume 堆渣量(万 m³)  --height 最大堆渣高度(m)
          --region 山区丘陵|平原滨海（防洪标准分区）
          --hazard 严重|较严重|不严重|较轻|无危害（可选）
          --method bishop|swedish（抗滑计算方法）
          --case normal|abnormal（正常/非常运用）  --calc-k 报告计算值

【退出码】
    0 = 定级成功（未复核 K 或 K 满足）；1 = K 不满足；2 = 参数不足 / 非法。
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 表 5.7.1：渣场级别 → (堆渣量下限/上限, 高度下限/上限, 危害程度)
#   区间：1 级 V∈[1000,2000] H∈[150,200]；2 级 V∈[500,1000) H∈[100,150)；3 级 V∈[100,500) H∈[60,100)
#         4 级 V∈[50,100)   H∈[20,60)；  5 级 V<50 或 H<20
LEVEL_BY_VOLUME = [(1000, 1), (500, 2), (100, 3), (50, 4), (0, 5)]      # (下限, 级别)，取满足的最大下限
LEVEL_BY_HEIGHT = [(150, 1), (100, 2), (60, 3), (20, 4), (0, 5)]
HAZARD_LEVEL = {"严重": 1, "较严重": 2, "不严重": 3, "较轻": 4, "无危害": 5}

# 表 5.7.2：渣场级别 → 拦渣堤/拦渣坝/挡渣墙/排洪工程 建筑物级别
BLDG_LEVEL = {
    1: {"拦渣堤": 1, "拦渣坝": 1, "挡渣墙": 2, "排洪工程": 1},
    2: {"拦渣堤": 2, "拦渣坝": 2, "挡渣墙": 3, "排洪工程": 2},
    3: {"拦渣堤": 3, "拦渣坝": 3, "挡渣墙": 4, "排洪工程": 3},
    4: {"拦渣堤": 4, "拦渣坝": 4, "挡渣墙": 5, "排洪工程": 4},
    5: {"拦渣堤": 5, "拦渣坝": 5, "挡渣墙": 5, "排洪工程": 5},
}

# 表 5.7.3：建筑物级别 → 防洪标准[重现期(年)]  (设计, 校核)
FLOOD_STD = {
    # 级别: (山区丘陵设计, 山区丘陵校核, 平原滨海设计, 平原滨海校核)
    1: ("100", "200", "50", "100"),
    2: ("100~50", "200~100", "50~30", "100~50"),
    3: ("50~30", "100~50", "30~20", "50~30"),
    4: ("30~20", "50~30", "20~10", "30~20"),
    5: ("20~10", "30~20", "10", "20"),
}

# 表 5.7.4-1 / -2：弃渣场抗滑稳定安全系数
K_BISHOP = {"normal": {1: 1.35, 2: 1.30, 3: 1.25, 4: 1.20, 5: 1.20},
            "abnormal": {1: 1.15, 2: 1.15, 3: 1.10, 4: 1.05, 5: 1.05}}
K_SWEDISH = {"normal": {1: 1.25, 2: 1.20, 3: 1.20, 4: 1.15, 5: 1.15},
             "abnormal": {1: 1.10, 2: 1.10, 3: 1.05, 4: 1.05, 5: 1.05}}

# 表 5.7.5-1：挡渣墙基底抗滑稳定安全系数（土质地基 / 岩石地基·抗剪强度）
K_WALL_SOIL = {"normal": {1: 1.35, 2: 1.30, 3: 1.25, 4: 1.20, 5: 1.20},
               "abnormal": {1: 1.10, 2: 1.10, 3: 1.10, 4: 1.05, 5: 1.05}}
K_WALL_ROCK = {"normal": {1: 1.10, 2: 1.08, 3: 1.08, 4: 1.05, 5: 1.05},
               "abnormal": {1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00}}
# 表 5.7.5-1：岩石地基按抗剪断公式（不随级别变化）
K_WALL_ROCK_FRACTURE = {"normal": 3.00, "abnormal": 2.30}
# 表 5.7.5-2：土质地基挡渣墙抗倾覆安全系数（1/2/3/4、5 级）
K_OVERTURN = {"normal": {1: 1.60, 2: 1.50, 3: 1.45, 4: 1.40, 5: 1.40},
              "abnormal": {1: 1.50, 2: 1.40, 3: 1.35, 4: 1.30, 5: 1.30}}
# 表 5.7.5-3：拦渣堤抗滑稳定安全系数（计条块间作用力）
K_DIKE_SLIDE = {"normal": {1: 1.35, 2: 1.30, 3: 1.25, 4: 1.20, 5: 1.20},
                "abnormal": {1: 1.15, 2: 1.15, 3: 1.10, 4: 1.05, 5: 1.05}}


def level_by(value, table):
    for lo, lv in table:
        if value >= lo:
            return lv
    return 5


def main():
    ap = argparse.ArgumentParser(description="弃渣场级别与防护标准复核（GB 51018-2014 §5.7）")
    ap.add_argument("--volume", type=float, required=True, help="堆渣量 V（万 m³）")
    ap.add_argument("--height", type=float, required=True, help="最大堆渣高度 H（m）")
    ap.add_argument("--region", default="山区丘陵", choices=["山区丘陵", "平原滨海"], help="防洪标准分区")
    ap.add_argument("--hazard", choices=list(HAZARD_LEVEL.keys()), help="失事危害程度（可选）")
    ap.add_argument("--method", default="bishop", choices=["bishop", "swedish"], help="抗滑计算方法")
    ap.add_argument("--case", default="normal", choices=["normal", "abnormal"], help="运用状况")
    ap.add_argument("--calc-k", type=float, help="报告给出的抗滑安全系数（可选，用于复核）")
    ap.add_argument("--wall-level", type=int, choices=[1, 2, 3, 4, 5], help="挡渣墙级别（默认随渣场级别取表 5.7.2）")
    ap.add_argument("--wall-foundation", default="soil", choices=["soil", "rock"], help="挡渣墙地基：土质(soil)/岩石(rock)")
    ap.add_argument("--wall-k", type=float, help="报告给出的挡渣墙基底抗滑安全系数（可选）")
    ap.add_argument("--overturn-k", type=float, help="报告给出的挡渣墙抗倾覆安全系数（可选，土质地基）")
    args = ap.parse_args()

    if args.volume < 0 or args.height < 0:
        print("参数非法：堆渣量与高度须为非负数。")
        return 2

    lv_v = level_by(args.volume, LEVEL_BY_VOLUME)
    lv_h = level_by(args.height, LEVEL_BY_HEIGHT)
    lv_candidates = [lv_v, lv_h]
    notes = ["按堆渣量 V=%.0f 万m³ → %d 级" % (args.volume, lv_v),
             "按最大堆渣高度 H=%.0f m → %d 级" % (args.height, lv_h)]
    if args.hazard:
        lv_hz = HAZARD_LEVEL[args.hazard]
        lv_candidates.append(lv_hz)
        notes.append("按危害程度『%s』 → %d 级" % (args.hazard, lv_hz))

    lv = min(lv_candidates)   # 就高不就低 = 取最小级别号
    print("== 弃渣场定级（GB 51018-2014 表 5.7.1）==")
    for n in notes:
        print("   " + n)
    print("   → 综合定级：%d 级（就高不就低）" % lv)

    bl = BLDG_LEVEL[lv]
    print()
    print("== 拦挡工程建筑物级别（表 5.7.2，渣场 %d 级）==" % lv)
    print("   拦渣堤=%d级  拦渣坝=%d级  挡渣墙=%d级  排洪工程=%d级"
          % (bl["拦渣堤"], bl["拦渣坝"], bl["挡渣墙"], bl["排洪工程"]))
    print("   注：拦渣工程高度 ≥15m 且渣场为 1、2 级时，挡渣墙级别可提高 1 级。")

    # 防洪标准
    i = 0 if args.region == "山区丘陵" else 2
    print()
    print("== 防洪标准（表 5.7.3，%s）==" % args.region)
    for name in ("拦渣堤", "拦渣坝"):
        code = bl[name]
        d, c = FLOOD_STD[code][i], FLOOD_STD[code][i + 1]
        print("   %s（%d级）：设计 %s 年 | 拦渣堤/坝不设校核" % (name, code, d))
    code = bl["排洪工程"]
    d, c = FLOOD_STD[code][i], FLOOD_STD[code][i + 1]
    print("   排洪工程（%d级）：设计 %s 年 | 校核 %s 年" % (code, d, c))
    print("   临时性拦挡：3~5 年一遇；渣场为 3 级以上时可提高到 10 年一遇。")
    print("   永久性截排水：3~5 年一遇 5~10min 短历时设计暴雨。")

    # 抗滑稳定
    kt = (K_BISHOP if args.method == "bishop" else K_SWEDISH)
    kstd = kt[args.case][lv]
    mname = {"bishop": "简化毕肖普法/摩根斯顿-普赖斯法", "swedish": "瑞典圆弧法/改良圆弧法"}[args.method]
    cname = {"normal": "正常运用", "abnormal": "非常运用"}[args.case]
    tbl = "5.7.4-1" if args.method == "bishop" else "5.7.4-2"
    print()
    print("== 弃渣场抗滑稳定安全系数（表 %s，%s）==" % (tbl, mname))
    print("   %s 允许值：≥ %.2f" % (cname, kstd))
    rc = 0
    if args.calc_k is not None:
        ok = args.calc_k >= kstd
        print("   报告值：%.2f  → %s" % (args.calc_k, "满足" if ok else "★不满足"))
        rc = 0 if ok else 1
    else:
        print("   （未给 --calc-k，仅出允许值）")

    # 表 5.7.5：挡渣墙 / 拦渣堤 稳定
    wl = args.wall_level or bl["挡渣墙"]
    fname = "土质地基" if args.wall_foundation == "soil" else "岩石地基"
    print()
    print("== 挡渣墙稳定（表 5.7.5，挡渣墙 %d 级，%s）==" % (wl, fname))
    if args.wall_foundation == "soil":
        ks = K_WALL_SOIL[args.case][wl]
        print("   基底抗滑允许值（土质地基）：≥ %.2f" % ks)
    else:
        ks = K_WALL_ROCK[args.case][wl]
        kr = K_WALL_ROCK_FRACTURE[args.case]
        print("   基底抗滑允许值（岩石地基·抗剪强度）：≥ %.2f" % ks)
        print("   基底抗滑允许值（岩石地基·抗剪断公式）：≥ %.2f" % kr)
    if args.wall_k is not None:
        ok = args.wall_k >= ks
        print("   报告基底抗滑值：%.2f → %s" % (args.wall_k, "满足" if ok else "★不满足"))
        if not ok:
            rc = 1
    ko = K_OVERTURN[args.case][wl]
    print("   土质地基抗倾覆允许值（表 5.7.5-2）：≥ %.2f" % ko)
    if args.overturn_k is not None:
        ok2 = args.overturn_k >= ko
        print("   报告抗倾覆值：%.2f → %s" % (args.overturn_k, "满足" if ok2 else "★不满足"))
        if not ok2:
            rc = 1
    kd = K_DIKE_SLIDE[args.case][lv]
    print("   拦渣堤抗滑允许值（表 5.7.5-3）：≥ %.2f" % kd)

    print()
    print("依据：GB 51018-2014 5.7.1/5.7.2/5.7.3/5.7.4/5.7.5；强条另见 12.2.2（选址）。")
    return rc


if __name__ == "__main__":
    sys.exit(main())
