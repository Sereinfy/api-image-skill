# api-image

`api-image` 是供 Codex App 使用的图像生成与编辑 Skill。它让 Codex 通过当前用户配置的 OpenAI 兼容服务提供商调用图像 API，在不能或不应使用内置 `imagegen` 时完成文生图、参考图生成和图像编辑。

Codex 负责理解需求、按需研究资料、分析参考图、整理提示词和验证结果；随附脚本负责解析服务提供商配置、构建请求、调用 API 并保存图像。

## 功能

- 文生图：调用 `/images/generations`
- 参考图生成与图像编辑：调用 `/images/edits`
- 最多 16 张输入图像，并可通过 `--image-role` 标注每张图像的用途
- 蒙版局部编辑，以及蒙版格式、尺寸和 Alpha 通道校验
- 单条提示词、完整多行提示词文件和显式批量提示词列表
- 同一提示词生成 1 至 10 个变体
- `png`、`jpeg`、`webp` 输出格式及 `jpeg`/`webp` 压缩质量；显式指定格式时自动匹配输出扩展名
- 自定义尺寸、质量、背景、审核级别、超时和模型名称
- 严格成对解析 API 密钥与基础 URL，不跨优先级混用配置
- 优先读取 `b64_json`，并兼容返回图像 URL 的服务提供商
- 默认使用 `gpt-image-2`、`2048x1152`、`high` 质量和 1800 秒超时

详细的代理执行规则、研究要求和提示词规范见 [SKILL.md](./SKILL.md)。

## 必读：批量生成

**除非用户明确要求批量生成，否则不得使用 `--prompt-list`。**

- `--prompt-list` 必须与 `--batch` 同时使用。
- 不得根据多行、多段、多个主题、编号列表或文件名自行推断批量意图。
- 默认使用 `--prompt`，包括聊天、变量或命令参数中的多行内容。仅当提示词文件已经存在，或内容过长、命令行转义可能破坏原始格式时，才使用 `--prompt-file`。不得仅因内容包含多行或仅为使用该参数而创建临时文件。
- 只有用户明确要求“批量生成”“逐条生成列表”或“每行作为一条独立提示词”时，才使用 `--prompt-list <path> --batch`。

## 环境要求

- Codex App
- Python 3.11 或更高版本
- 一个支持 OpenAI 兼容图像端点的服务提供商
- 可选：Pillow。未安装时，脚本仍可直接检查 PNG、JPEG 和 WebP。

## 安装

将仓库克隆到 Codex 的 skills 目录：

```powershell
git clone <repo-url> "$env:USERPROFILE\.codex\skills\api-image"
```

如果设置了 `CODEX_HOME`：

```powershell
git clone <repo-url> "$env:CODEX_HOME\skills\api-image"
```

随后重启 Codex App，或让 Codex 重新加载 Skills。

## 配置服务提供商

脚本始终将 API 密钥和基础 URL 视为同一配对，按以下优先级选择第一组有效配置：

1. 本次命令明确传入的临时配对
2. Skill 目录中的 `api-image.toml`
3. `OPENAI_IMAGE_API_KEY` 与 `OPENAI_IMAGE_BASE_URL`
4. `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`
5. Codex 根目录中的 `auth.json` 与 `config.toml`

命令行覆盖和环境变量配对必须完整，否则直接报错。`api-image.toml` 需要 `base_url`；密钥优先使用 `api_key`，没有时使用 `api_key_env` 指定的环境变量。两个密钥字段都没有时，该层跳过并继续使用下一级配置；已指定但无效的环境变量仍会直接报错。

### 方式一：api-image.toml

`api-image.toml` 位于 Skill 根目录。文件需要基础 URL，并可直接保存密钥或保存密钥所在的环境变量名。两者同时存在时优先使用 `api_key`，不建议把真实密钥写入文件：

```toml
base_url = "https://provider.example.com/v1"
# api_key = "<你的 API 密钥>"
api_key_env = "API_IMAGE_API_KEY"
```

如果不使用 `api_key`，可在 PowerShell 中设置 `api_key_env` 指定的密钥：

```powershell
$env:API_IMAGE_API_KEY = "<你的 API 密钥>"
```

将 `base_url` 和两个密钥字段都留空可禁用此配置层；只提供 URL 但没有密钥字段时也会跳过此层并继续回退：

```toml
base_url = ""
api_key = ""
api_key_env = ""
```

### 方式二：图像专用环境变量

```powershell
$env:OPENAI_IMAGE_API_KEY = "<你的 API 密钥>"
$env:OPENAI_IMAGE_BASE_URL = "https://provider.example.com/v1"
```

### 方式三：通用环境变量

```powershell
$env:OPENAI_API_KEY = "<你的 API 密钥>"
$env:OPENAI_BASE_URL = "https://provider.example.com/v1"
```

### 方式四：Codex 根目录文件

未命中更高优先级配置时，脚本读取：

- `$CODEX_HOME/auth.json` 与 `$CODEX_HOME/config.toml`
- 未设置 `CODEX_HOME` 时读取 `~/.codex/auth.json` 与 `~/.codex/config.toml`

`auth.json` 必须包含 `OPENAI_API_KEY`。`config.toml` 必须包含 `model_provider`，以及对应 `[model_providers.<name>]` 下的 `base_url`。

不要将真实 API 密钥提交到仓库、README、日志或提示词文件中。

## 在 Codex 中使用

安装后直接用自然语言提出请求：

```text
用 api-image 生成一张 2048x1152 的电影感照片：雨夜东京街头，霓虹反光，真实摄影风格。
```

带参考图时：

```text
参考这张图的构图和人物姿势，生成一张暖色电影感插画。保持主体姿态，但不要照抄原图。
```

需要真实地点、产品、建筑、历史服饰或其他事实性主题时：

```text
先查花江峡谷大桥的结构和地形参考，再生成一张高空俯视图，尽量保持真实桥型和峡谷环境。
```

需要批量生成时，必须明确说明：

```text
批量生成这个提示词列表，每个非空行作为一条独立提示词。
```

## 直接运行脚本

脚本路径：

```text
<skill-dir>\scripts\generate_image.py
```

### 文生图

```powershell
python "<skill-dir>\scripts\generate_image.py" `
  --prompt "雨夜城市街道，电影感摄影，湿润路面反射霓虹" `
  --size "2048x1152" `
  --quality "high" `
  --out ".\outputs\city-night.png"
```

### 参考图生成或编辑

只要提供 `--image`，`--mode auto` 就会自动选择编辑端点：

```powershell
python "<skill-dir>\scripts\generate_image.py" `
  --prompt "参考输入图的构图和角色姿势，生成一张暖色电影感插画" `
  --image "C:\path\to\reference.png" `
  --image-role "构图和姿势参考" `
  --size "2048x2048" `
  --out ".\outputs\reference-output.png"
```

可重复使用 `--image` 和 `--image-role`。`--image-role` 数量不得超过 `--image` 数量。

### 蒙版局部编辑

第一张 `--image` 是编辑目标。蒙版必须与它格式相同、尺寸相同，并包含 Alpha 通道：

```powershell
python "<skill-dir>\scripts\generate_image.py" `
  --prompt "只把蒙版标出的区域替换成一只小水獭，保持其他区域不变" `
  --image "C:\path\to\source.png" `
  --mask "C:\path\to\mask.png" `
  --out ".\outputs\masked-edit.png"
```

### 将多行文件作为一条提示词

默认使用 `--prompt`。仅当提示词文件已经存在，或直接传参因内容过长、命令行转义可能破坏原始格式而不可靠时，才使用 `--prompt-file`。它会读取整个 UTF-8 文件，包括换行，并只发起一次提示词请求：

```powershell
python "<skill-dir>\scripts\generate_image.py" `
  --prompt-file ".\inputs\structured-prompt.md" `
  --out ".\outputs\single-image.png"
```

如果多行内容直接来自用户消息、变量或命令参数，将完整内容作为一条 `--prompt` 传入。不得仅因内容包含多行或仅为使用 `--prompt-file` 而创建临时文件。

### 显式批量生成

仅在用户明确要求批量生成时使用。列表中每个非空行是一条独立提示词：

```powershell
python "<skill-dir>\scripts\generate_image.py" `
  --prompt-list ".\inputs\asset-prompts.txt" `
  --batch `
  --out ".\outputs\batch.png"
```

`--prompt`、`--prompt-file` 和 `--prompt-list` 必须且只能使用一个。`--batch` 只能与 `--prompt-list` 一起使用。

### 临时切换服务提供商

临时覆盖必须同时提供 URL 和 API 密钥。优先从环境变量读取密钥：

```powershell
$env:JOB_IMAGE_API_KEY = "<临时 API 密钥>"
python "<skill-dir>\scripts\generate_image.py" `
  --prompt "一张赛博朋克风格的夜景照片" `
  --base-url "https://provider.example.com/v1" `
  --api-key-env "JOB_IMAGE_API_KEY" `
  --out ".\outputs\temporary-provider.png"
```

也可以使用 `--base-url-env` 从环境变量读取 URL。临时覆盖不会写回 `api-image.toml`、`auth.json` 或 `config.toml`。

也可以使用 `--api-key "<临时 API 密钥>"` 直接传入一次性密钥；不要与 `--api-key-env` 同时使用。

## 参数与限制

| 参数 | 行为与限制 |
| --- | --- |
| `--model` | 默认 `gpt-image-2` |
| `--mode` | `auto`、`generate` 或 `edit`；`auto` 在存在输入图像或蒙版时选择 `edit` |
| `--size` | 默认 `2048x1152`；支持 `auto` 或有效的 `宽x高` |
| `--quality` | `low`、`medium`、`high`、`auto`；默认 `high` |
| `--n` | 每条提示词生成的图像数，范围 1 至 10；默认 1 |
| `--image` | 可重复，最多 16 张；每张最大 50 MB |
| `--image-role` | 可重复，用于把输入图像角色附加到提示词 |
| `--mask` | 用于局部编辑；必须与第一张输入图像格式、尺寸一致并包含 Alpha 通道 |
| `--background` | `auto`、`opaque` 或 `transparent`；官方 `gpt-image-2` 的透明背景目前为 `preview`，需输出 `png` 或 `webp` |
| `--output-format` | `png`、`jpeg` 或 `webp` |
| `--output-compression` | 0 至 100；仅与 `jpeg` 或 `webp` 一起使用 |
| `--input-fidelity` | 支持该参数的编辑模型可用 `low` 或 `high`；不得传给 `gpt-image-2` |
| `--moderation` | 支持该参数的模型可用 `auto` 或 `low` |
| `--codex-home` | 临时指定 Codex 根目录 |
| `--timeout` | 默认 1800 秒；设为 `0` 表示禁用客户端超时 |
| `--out` | 输出路径；显式指定 `--output-format` 时自动使用对应扩展名 |

自定义尺寸必须同时满足：

- 宽和高都是 16 的倍数
- 最长边不超过 3840 像素
- 长宽比不超过 3:1
- 总像素数在 655,360 至 8,294,400 之间

常见有效尺寸包括 `1024x1024`、`1536x1024`、`1024x1536`、`2048x1152`、`2048x2048`、`3840x2160` 和 `2160x3840`。

如果通过 `--output-format` 指定格式，脚本会将 `--out` 的扩展名自动调整为对应格式（例如 `result.png` + `--output-format webp` 会保存为 `result.webp`）。

## 端点与响应

- 纯文本生成：`POST <base_url>/images/generations`，JSON 请求体
- 输入图像、参考图或蒙版：`POST <base_url>/images/edits`，multipart 表单
- 优先从 `data[].b64_json` 解码图像
- `b64_json` 不存在时，兼容读取 `data[].url`
- 服务提供商返回 HTTP 错误时，脚本直接显示状态码和响应正文，不会改用其他服务提供商重试

## 输出文件

指定 `--out` 时使用该路径；指定 `--output-format` 后会自动替换为对应扩展名。未指定扩展名且没有指定输出格式时默认使用 `.png`。未指定 `--out` 时，在当前目录生成：

```text
provider-image-YYYYMMDD-HHMMSS.<format>
```

其中 `<format>` 为 `--output-format` 指定的格式；未指定时为 `png`。

多结果使用确定性后缀：

- 同一提示词的多个变体：`-v1`、`-v2` 等
- 多条批量提示词：`-p1`、`-p2` 等
- 批量提示词且每条有多个变体：`-p1-v1`、`-p1-v2` 等

脚本会创建缺失的输出目录，并将每个最终绝对路径打印到标准输出。

## 常见错误

- `api-image.toml` 只提供密钥字段但缺少 `base_url`：补齐 URL；只提供 URL 且没有密钥字段时，该层会跳过并继续回退。
- `api-image.toml` 指定的密钥环境变量未设置：设置该变量，或移除该字段后让配置继续回退到下一级。
- `--prompt-list` 没有同时使用 `--batch`：确认用户明确要求批量后再同时传入。
- 编辑模式没有 `--image`：至少提供一张编辑目标或参考图。
- 蒙版校验失败：确保蒙版与第一张输入图像格式、尺寸一致，并包含 Alpha 通道。
- `gpt-image-2` 使用 `input_fidelity`：移除该参数；使用透明背景时确认输出格式为 `png` 或 `webp`。
- 图像尺寸不合法：检查 16 倍数、最长边、长宽比和总像素数限制。

## 测试

在项目根目录运行：

```powershell
python -m unittest discover -s .\\tests -v
```

测试覆盖配置密钥优先级、输出扩展名匹配和透明背景参数校验。

## 目录结构

```text
api-image/
├── SKILL.md
├── README.md
├── api-image.toml
├── agents/
│   └── openai.yaml
└── scripts/
    ├── generate_image.py
    ├── provider_imagegen/
└── tests/
    ├── __init__.py
    └── test_provider_imagegen.py
```

## 许可证与致谢

MIT License。

感谢 [linux.do](https://linux.do/) 社区的交流、分享与反馈。
