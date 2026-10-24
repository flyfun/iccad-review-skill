# 审查数据与证据契约 v1.0（水利）

本契约是套件内部工作记录格式，**不是**国家标准、审查规程或法定审签格式。脚本只校验记录关系与数值复算，不验证操作者身份、资质和工程结论。

机器可读的完整字段定义以 `scripts/validate_review.py` 的校验逻辑为准；本文件说明每个字段的**语义与禁止事项**。两者冲突时以脚本行为为准并同步修订本文件。

## 工作基线 project

- `schema_version`：`1.0`。
- `mode`：`project`（实际项目）或 `synthetic`（合成演示）。合成演示不得表示实际工程通过。
- `project` 字段：

| 字段 | 说明 |
|---|---|
| `id` `name` | 项目标识与名称 |
| `region` | 省/市/县；跨省项目写主要受影响行政区 |
| `project_type` | 水库、水闸、泵站、堤防、灌区、河道治理、涉河桥梁、引调水等 |
| `module` | 主审查模块 `M1`~`M14`，与 `iccad-route` 判定一致 |
| `modules_extra` | 跨模块报告涉及的附加模块数组；不可只取主模块 |
| `stage` | `proposal` 项建、`feasibility` 可研、`preliminary` 初设、`construction_doc` 技施、`special` 专项报告、`safety_appraisal` 安全鉴定、`design_change` 重大变更、`evaluation` 评价评估 |
| `grade` | 工程等别 `I`~`V`；未知填 null 并记缺口，不要猜。等别影响阈值取值 |
| `review_date` `baseline_date` | 本次审查日与资料基线日（ISO 日期） |
| `baseline_id` | 本轮报告基线标识（如 `送审稿V2`），闭环复查必须对应它 |
| `scope_ref` | 审查范围引用（任务书/委托单编号或路径） |
| `planned_check_ids` | 本轮计划检查项 ID 数组，**先规划再执行** |
| `requested_disciplines` | 本次涉及的专业枚举 |
| `data_class` `processing` | 数据级别与处理环境 |

- discipline 枚举：`general`、`hydrology`、`dam`、`gate_pump`、`geotech`、`hydraulic`、`structure`、`flood_eval`、`soil_water`、`water_resource`、`environment`、`resettlement`、`cost`、`coordination`。
- `processing`：`mode=local/cloud`、`environment_verified` 布尔、`authorization_ref`、`sanitization_ref`。声明 verified 只是**存在核验记录**，不是脚本验证了网络隔离。未分类或受限内容不应进入不适当的模型会话。
- `conclusion`：审查结论，仅记录**人工**结论。`status` 取 `pending`、`pass`（通过）、`pass_with_revision`（修改后通过）、`fail`（不通过）。非 pending 必须有 `actor`、`at`、`record_ref`、`note`。AI 不得填写本人以外的主体，也不得把 AI 判断写成结论。

## 来源 sources

字段：`id`、`path`、`sha256`、`revision`、`discipline`、`capability`、`locator_convention`。

- `path` 相对本次资料根目录或绝对路径；绝对路径仍须位于 `--root` 内。
- 哈希对**字节内容**计算（64 位小写十六进制），不能以文件名、日期或页数代替。
- 报告正文、附表、图纸目录、计算书、批复文件、OCR 文字、转换件各有来源 ID；转换或摘录须记录原来源与过程（写在 `revision` 或 `locator_convention`）。
- `capability` 记录本来源**可支持什么**（如 `text`、`tables`、`drawing_list_only`、`scanned_image`）。扫描件只能支持图像层面核对，不能声称已读取图元。
- 清单脚本输出是**候选清单**，不自动获得签发权威性。

## 依据 bases

字段：`id`、`kind`、`title`、`identifier`、`clause`、`source_ref`、`authority`、`level`、`mandatory`、`status`、`applicability`、`effective_from`、`effective_to`、`verified_at`、`verified_by`、`transition_ref`、`rights_basis`、`summary`。

- `kind`：`standard`（规范标准）、`regulation`（法规/部委文件/规程性通知）、`approval`（批复/审查意见）、`drawing`（图纸）、`project`（项目专用技术要求）。
- `authority`：`official`、`project_approved`、`synthetic`、`unknown`。`official` 必须有可追溯的官方公告、正文或受控副本，**不是凭名称认定**。院内批准本身不能把非规范材料变成规范。
- `level`：`gb` 国标、`sl` 水利行标（SL）、`sl_t` 水利推荐性（SL/T）、`db` 地标、`tb` 团体标准、`internal` 单位内部。推荐性标准**不得**标为强制性条文。
- `mandatory`：布尔，仅 `kind=standard` 且确有强条时可为 true。`true` 必须有 `clause` 与可追溯来源，否则记 unknown。
- `status`：`effective`、`superseded`、`future`、`unknown`、`synthetic`。
- `applicability`：`confirmed`、`unknown`、`not_applicable`。地域、工程类型、阶段适用性都要在 `summary` 里说明依据。
- 已核验 standard 必须有可解析的实施起日；有效区间为 `[effective_from, effective_to)`，`effective_to` 为空表示**未记录终止日**，不证明永久有效。
- `status=unknown` 时，未知的 `identifier`/`clause`/`source_ref`/`verified_by`/`verified_at`/`rights_basis`/`effective_from` 可用 null，保留 `title`、`summary` 和检索缺口；**不得为了通过格式检查编造元数据**。关联规则保持 `draft`，检查记 `unverified_basis`。
- 基准日超出有效区间，或 `status` 为 `superseded`/`future` 时，只有项目适用性已确认且提供 `transition_ref`（真实过渡规定或经授权的适用性决策引用），才能作为本项目有效依据。**不得仅凭填入非空字符串认定过渡有效**。
- `summary` 仅摘要，不在本套件分发授权不明的标准全文。`rights_basis` 记录本次使用范围。

## 规则 rules

字段：`id`、`version`、`discipline`、`basis_ids`、`applicability`（`state`/`rationale`）、`status`（`draft`/`verified`/`disabled`）、`verified_by`、`verified_at`、`verification_ref`、`test_ref`、`criterion`。

- `criterion` 至少含 `kind`、`quantity`、`object_scope`、`basis_locator`、`explanation`。
  - `kind=numeric` 另含 `operator`（`ge`/`le`/`gt`/`lt`/`eq`）、`threshold`、`unit`；`eq` 可含 `tolerance`（与 `unit` 同量纲）。
  - `kind=qualitative` / `consistency` / `completeness` 说明如何判别及必须保留的证据。
- `verified` 是**人工确认后**的工作记录，AI 不得伪造责任人或验证文件。
- `draft` 的未知 `basis_locator`、`operator`、`threshold`、`unit` 可为 null，获得适用依据后再填；**draft 不得作为 evaluated 的规则**。不要为通过校验猜阈值。
- 内置数值检查器只支持脚本 `UNITS` 表列明的单位与精确十进制换算；不支持的流量口径、复合单位、修约与工程容差须由经验证的专项工具处理并保留方法，**不擅自换成近似值**。

## 计划和执行 checks

字段：`id`、`rule_id`、`origin`、`engine_ref`、`basis_ids`、`source_ids`、`status`、`result`、`reason`、`evidence`、`comparison`。

- `origin`：`plan`（来自 `iccad-route` 计划项）、`engine`（来自确定性引擎预扫候选）、`manual`（人工补充）。
- `origin=engine` 时 `rule_id` 可为 null，但必须有 `engine_ref` 指向具体检查器/探针名；引擎候选**置信度不高于 medium**，须人工复核后才可作为疑点定稿。

| status | result | 含义 |
|---|---|---|
| `evaluated` | `signal`/`no_signal` | 有适用依据（或等价 engine_ref）且输入可评估，保留证据；`signal` 必有对应 finding |
| `not_applicable` | null | 有明确不适用理由；纳入覆盖分母但不算已求值 |
| `insufficient_input` | null | 材料或必要字段缺失 |
| `unsupported` | null | 当前工具不具备所需识别/计算能力（如无 DWG 图元解析） |
| `unverified_basis` | null | 依据或适用性未能核验 |
| `error` | null | 解析、规则或工具执行失败 |

- 每个 `planned_check_ids` 必须有且只有一条 check，**禁止执行后删掉未完成项**。计划清单来自任务范围和经确认的专业矩阵，不能为了门禁通过而只规划一项。脚本不能判断范围是否足够全面。
- 每条 evidence：`source_id`、`source_sha256`、`locator`、`excerpt`。`locator` 用章节号/表号/图号/页码/单元格/条文号；必要时补 `bbox`、`view`。截图必须能回到原始来源。对「未找到」说明检索范围，**不能把未知归零**。
- `comparison`（numeric）：`quantity`、`object_ref`、`observed_value`、`observed_unit`、`normalized_value`、`normalized_unit`、`operator`、`threshold`、`threshold_unit`、`conditions_verified`、`conditions_ref`、`evidence_index`。对象语义和前提须由正文/计算书核对，脚本不能核验两者。数值用 JSON number 或十进制字符串，未知用 null 并记 `insufficient_input`，**不用 0 代替**。

## 疑点 findings

字段：`id`、`check_id`、`kind`、`discipline`、`title`、`observation`、`priority`、`confidence`、`basis_ids`、`evidence`、`suggested_action`、`review`、`closure`。

- `kind`：
  - `rule_deviation`：偏离已核验规则/强条，须有可定位证据；
  - `document_conflict`：至少两个**不同** `source_id`，且时间/基线可比较（如正文与附表、正文与图纸目录）；
  - `calculation_inconsistency`：计算书/公式/参数与正文引用结果不一致，须给出两侧定位与数值；
  - `missing_information`：关联「应提供该资料」的要求与已检索范围。
- `priority`：`P1`（涉及防洪安全、结构安全、强制性条文或关键结论链，优先核实）、`P2`（功能、规模、投资或跨篇章协调）、`P3`（表达、体例与一般资料）。这是**工作分流**，不替代缺陷定级。
- `confidence`：`high`/`medium`/`low`，表示证据可靠程度。数值置信度若未校准不视为概率。**优先级与置信度不可互相代替**：P1 低置信疑点仍可优先复核。
- 不用 AI 的「通过/不通过/合规/不合规」替代人工结论；允许在 evidence 中如实引用原文判断词，也允许忠实转述已有人工结论并注明来源。
- `review.status`：`pending`/`adopted`/`not_applicable`/`undetermined`。非 pending 要有 `actor`、`at`、`record_ref`、`note`，**只能按实际人工记录写入**。`adopted` 不是已整改，`undetermined` 仍未闭环。不适用处置另需当前 `baseline_id`。
- `closure.status`：`open`/`response_submitted`/`recheck_required`/`closed`/`not_applicable`；另含 `response`、`revision_source_ids`、`recheck`（`actor`、`at`、`record_ref`、`baseline_id`、`evidence`）。`closed` 要有已采用的人工复核、修订来源和**本轮基线**复查证据；`not_applicable` 要有人工不适用记录及理由。
- **单纯设计回复或材料上传不能自动关闭问题**。新版本修改证据后重查相关项，保留旧版本和事件记录，不覆盖旧结论。

## 三类校验

1. **结构校验**：ID 唯一、枚举、证据引用、哈希格式、日期、状态关系、数值复算。待定或缺材料可以仍是结构有效的工作稿。
2. **`--verify-files`**：另核对所有声明来源位于允许目录内且字节哈希一致。此步不证明文件签发状态或真实性。
3. **`--gate`**：强制重新核对来源，检查计划全覆盖、实际求值、依据确认、无规则错误、疑点人工复核、P1 闭环与结论记录，给出 `ready_for_human_signoff` 或阻塞清单。

`ready_for_human_signoff` 仅表示记录满足本套件的**审签准备规则**；不得据此输出「工程已通过审查」。外发、注册签章、身份验证与不可篡改存证依实际平台。

## 与确定性引擎的关系

本契约不依赖任何引擎。若接入 `iccad-review` 引擎（零 Token 规则扫描），其输出通过 `scripts/import_scan.py` 转成 `origin=engine` 的候选 check：

- 引擎命中**不得**直接写成已定稿疑点；`confidence` 不高于 `medium`，`review.status` 一律 `pending`。
- 引擎给出的 `quote` 为空时，只能记 `insufficient_input` 并注明「引擎命中但无可定位片段」，**不得补造引文**。
- 引擎的领域自动判定（`domain_source=auto`）已知存在偏差（如灌区渠系被判为水闸），计划检查项须以 `iccad-route` 的判定为准并在记录中保留引擎原判备查。
