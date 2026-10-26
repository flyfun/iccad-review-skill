# 接入 ima 知识库（规范原文检索）

本套件**不内置**检索脚本之外的任何外部依赖。接入 ima 的目的是解决一个具体问题：
[规范依据核验](workflow/02-standards.md) 要求「引用条文必须能回到原文」，而条文原文通常在几十份 PDF 里，靠模型记忆写条号是最危险的做法。

ima 提供知识库检索，能把「这条规范第几款规定什么」问到出处。它**替代不了**对现行性与适用性的判断。

## 三种接入方式

| 方式 | 适用 | 需要密钥 | 在审查中的用法 |
|---|---|---|---|
| A 宿主连接器（推荐） | WorkBuddy / 支持 MCP 的宿主 | 否（宿主内授权） | Agent 直接调用检索工具 |
| B OpenAPI 凭据 | 本机脚本、CI、命令行 | 是 | `scripts/ima_probe.py` 自检与手工检索 |
| C 既有引擎 CLI | 已装 `iccad-review` 引擎 | 是（同 B） | `wsl_ima.py --spec/--search` |

三者最终打的都是同一个服务：`https://ima.qq.com`。

## 方式 A：宿主连接器

1. 在宿主的连接器/插件市场找到 **ima**，完成授权（扫码或账号授权）。
2. 授权后用只读操作自检：列出知识库。能看到至少一个知识库即通。
3. 审查时由 Agent 直接检索，无需你贴密钥。

优点：零配置、密钥由宿主保管。限制：只能在该宿主内使用，命令行脚本拿不到这条通路。

## 方式 B：OpenAPI 凭据（脚本用）

### 1. 获取

打开 `https://ima.qq.com/agent-interface`，生成 **Client ID** 与 **API Key**。
需要先在 ima 客户端创建知识库并上传规范文件（解析完成后再检索，未解析的文件搜不到内容）。

### 2. 存放（二选一）

```bash
# 二选一①：文件（推荐，不污染 shell 环境）
mkdir -p ~/.config/ima
printf '%s' '你的 Client ID' > ~/.config/ima/client_id
printf '%s' '你的 API Key'   > ~/.config/ima/api_key
chmod 600 ~/.config/ima/client_id ~/.config/ima/api_key

# 二选一②：环境变量
export IMA_OPENAPI_CLIENTID='你的 Client ID'
export IMA_OPENAPI_APIKEY='你的 API Key'
```

环境变量优先于文件；也接受旧名 `IMA_CLIENT_ID` / `IMA_API_KEY`。

### 3. 自检

```bash
python skills/iccad-review/scripts/ima_probe.py
python skills/iccad-review/scripts/ima_probe.py --search 压实度 --kb 规范库
```

正常输出形如：

```
连通正常，可见知识库 1 个（凭据来源：file）
  flyfun的知识库  (ima_kb_xxxxxxxx)
```

检索命中会列出知识库名、文件名与高亮片段。**高亮片段是摘要，不是条文原文**，引用前要打开文件核对。

### 4. 错误码对照

| 输出 | 含义 | 处理 |
|---|---|---|
| `reason: no_credentials` | 没找到凭据 | 按上面第 2 步写入，注意 Windows 下 `~` 指 `C:\Users\<你>` |
| `code 200002` / `credential_invalid` | 服务端拒绝凭据（`skill auth failed`） | Key 失效或被轮换，回控制台重新生成并覆盖 |
| `network_error` | 连不上 | 检查网络；脚本已 `ProxyHandler({})` 绕过系统代理，若公司网络强制代理需另配 |
| `no_knowledge_base` | 知识库为空 | 先在 ima 客户端建库上传文件 |
| `kb_not_found` | `--kb` 名字没匹配上 | 先不带 `--kb` 跑一次看列表，用名字片段或 id |
| 命中 0 条 | 文件未解析完，或检索词太泛 | 换条文关键词；确认文件状态为「解析成功」 |

接口细节（供二次开发）：`POST /openapi/wiki/v1/search_knowledge_base`（`{"query":"","cursor":"","limit":20}`）与
`POST /openapi/wiki/v1/search_knowledge`（`{"query":q,"cursor":"","knowledge_base_id":id}`），
请求头 `ima-openapi-clientid`、`ima-openapi-apikey`、`ima-openapi-ctx`。

## 方式 C：既有引擎 CLI

已安装 `iccad-review` 确定性引擎时，同一套凭据可直接用：

```bash
python scripts/wsl_ima.py --check              # 诊断凭据/网络/接口
python scripts/wsl_ima.py --list               # 列出知识库
python scripts/wsl_ima.py --search 消能防冲     # 全库检索
python scripts/wsl_ima.py --spec SL/T 619-2021 # 本地查新 + ima 找原文
```

## 在审查流程里的位置

```
workflow/02-standards.md
  1) ima 检索：拿到文件名、章节、条款片段
  2) 打开原文核对：条号、款号、文字是否一致
  3) 官方来源核对：现行 / 被替代 / 未生效、实施日期
  4) 写依据卡 bases：identifier、clause、status、applicability、source_ref、verified_by/at
```

**三条铁律**

1. **命中不等于依据**。检索结果只是线索；`authority=official` 仍需可追溯的官方公告或受控副本。
2. **不得把摘要当条文原文**。高亮片段可能截断或跨段拼接，引用前必须开原文。
3. **不得跨版本混用**。同一规范在库里可能存了多个年份，检索命中哪一版就以哪一版为线索，最终仍以基准日适用的那一版为准。

## 涉密与外发提示

- 检索词会发往 `ima.qq.com`。**检索词本身也是外发内容**，不要带项目名称、地名、单位名等敏感信息，用规范术语即可（如「土石坝 压实度」）。
- 涉密或内部受限报告不应进入第三方检索链路。
- 凭据只发往 `ima.qq.com`；文件上传流程另有 COS 临时凭据，与你的 Client ID / API Key 无关。
- 凭据不要写进仓库、脚本或提交记录。

## 与套件校验的关系

ima 检索**不参与** `--gate` 判定。它只影响依据卡的质量：

- 依据已核验 → 检查项可 `evaluated`；
- 只有检索线索、没核对原文 → 依据保持 `status=unknown`，相关检查记 `unverified_basis`，`--gate` 会阻塞。

这样设计是为了防止「搜到一段话就当依据」变成可放行的审查意见。
