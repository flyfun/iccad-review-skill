# 来源与改编说明

## 结构来源

本套件的文件组织、证据契约、三层校验闸门、安装与元数据校验脚本，改编自开源项目
[aia-review-skills](https://github.com/liuqing0224/aia-review-skills)（建筑设计院 AI 辅助审查，15 个 Codex Skills）。

借鉴的具体做法：

| 做法 | 在本套件中的对应 |
|---|---|
| 多 Skill 套件 + 一个总控编排 | `iccad-review` + 15 个专业/流程 Skill |
| 共享「审查数据与证据契约」 | [review-contract.md](skills/iccad-review/references/review-contract.md) |
| 依据卡区分 `authority`/`status`/`applicability`，未知保留 unknown 而不编造 | 同上，并增加 `level`、`mandatory`（强条属性） |
| 检查项六状态（evaluated/not_applicable/insufficient_input/unsupported/unverified_basis/error） | 同上，语义一致 |
| 三类校验：结构 / `--verify-files` / `--gate`，退出码 0-2-3 | `validate_review.py` |
| 合成示例只验证脚本行为，不代表工程精度 | `assets/example-*.json`、`mode=synthetic` |
| `catalog.json` 作为元数据单一来源 + `validate_skills.py` | 同结构 |
| `install.py` 遇同名目录先停、`--check` 校验就位 | 同结构 |
| 「不替代人工判断、不输出合规结论」的措辞约束 | 全套件贯穿 |

## 领域改编

由房屋建筑多专业改为水利工程，主要改动：

1. **路由维度**：建筑「用途/分类/分区」→ 水利「工程模块 M1~M14 × 设计阶段」，新增独立 Skill `iccad-route`。
2. **专业枚举**：architecture/fire/structure/water/hvac/electrical/energy/coordination
   → hydrology/dam/gate_pump/geotech/hydraulic/structure/flood_eval/soil_water/water_resource/environment/resettlement/cost/coordination/general。
3. **依据体系**：增加规范层级（gb/sl/sl_t/db/tb/internal）与**强制性条文属性**；水利审查中「推荐性条文被当强条」是高频争议点。
4. **疑点类型**：增加 `calculation_inconsistency`（计算书与正文/图纸不一致），水利报告中此类问题占比高。
5. **数值单位表**：换成水利常用单位（万 m³、m³/s、万 kW、cm/s 量级的渗透系数需先换算等），仍只支持精确十进制因子。
6. **新增引擎桥**：`import_scan.py` 把既有的 `iccad-review` 确定性引擎输出导入为候选检查项，并规定「无引文不补造、命中不定稿」。
7. **结论记录**：`conclusion` 限定为人工结论（通过/修改后通过/不通过），AI 留空。

## 未沿用的部分

- 未复制参考项目的任何标准全文、院内规则或阈值——本套件不内置未核验的规范编号与工程阈值。
- 未沿用其建筑专业检查表内容；水利检查表依据公开技术规程的**章节结构**与常见审查要点编写，不含条文原文。
- 未引入其 `requirements-dev.txt` 中的测试依赖；本套件脚本全部为标准库。

## 水利领域参考

模块划分与常见问题类型的整理，参考了以下公开材料的结构（未复制正文）：

- 水利部《水利工程设计文件编制规程》系列对报告章节的划分（各阶段报告目录结构）。
- 水利部稽察与设计质量抽查通报中归纳的高频问题类型（数值阈值、强条落实、导流深度、概算口径等）。
- 洪水影响评价、水土保持方案、水资源论证、环境影响评价各自技术导则的章节逻辑。
- 安全鉴定与河湖健康评价/幸福河湖评估的「出等级、出星级」而非「出方案」的产出差异。

具体条号、阈值与现行性**必须在具体项目中逐项核验**，套件不提供这些数据。

## 许可

本套件为原创编写（结构改编自 MIT 类开源项目，仅借鉴组织方式与流程设计）。
使用时请自行确认引用标准文本的授权范围；`rights_basis` 字段用于记录本次使用范围。
