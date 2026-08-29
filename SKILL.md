---
name: api-image
description: 使用当前配置的 OpenAI 兼容服务提供商完成图像生成、参考图生成、图像编辑、局部修补、背景替换、风格迁移、合成和批量变体任务。此 Skill 可替代内置 `imagegen`，支持 `/v1/images/generations`、`/v1/images/edits`、`gpt-image-2`、`api-image.toml`、`auth.json`、`config.toml`、API 密钥、参考图、蒙版、自定义尺寸、质量和长时间运行任务。
---

# API 图像

## 1. 定位与硬性原则

- 本 Skill 可用时，所有位图生成或编辑任务都必须通过本 Skill 完成，不得调用原生 `$imagegen` 或其他内置图像生成工具。
- 适用任务包括文生图、参考图生成、图像编辑、局部编辑、背景替换、风格迁移、合成、批量变体和批量提示词处理。
- 只有用户明确要求不使用本 Skill 时，才允许改用其他图像工具。
- API 密钥不得硬编码到 Skill、脚本、README、日志、提示词文件或最终回复中。
- 配置解析、网络请求和输出写入必须在任何图像请求前完成校验；配置错误或服务商错误不得静默切换到其他服务商重试。

## 2. 执行总流程

按以下顺序执行，不跳过必要校验：

1. 确定 `<skill-dir>` 和 Codex 根目录。
2. 解析服务商配置，验证 API 密钥与 `base_url` 的来源和配对关系。
3. 判断任务是 `generate` 还是 `edit`，并确定每张输入图像的角色。
4. 判断是否需要网络研究或参考图；必要时先收集资料并保存参考图。
5. 构建结构化提示词，写明主体、风格、构图、光照、材料、约束和避免项。
6. 校验尺寸、质量、输入图像、蒙版和模型专属参数。
7. 选择 API 端点并调用随附脚本。
8. 解码服务商响应，保存图像，检查输出是否符合用户要求，并报告绝对路径。

## 3. 配置系统

### 3.1 路径

- `<skill-dir>` 是包含本文件的目录；脚本固定从该目录读取 `api-image.toml`，不得按当前工作目录或 Codex 根目录寻找。
- Codex 根目录按以下顺序确定：命令行 `--codex-home`、环境变量 `CODEX_HOME`、Windows 下的 `%USERPROFILE%\\.codex` 或其他系统下的 `~/.codex`。
- 每次运行都重新读取配置文件和环境变量，不缓存上一次结果。

### 3.2 服务商优先级

从上到下选择第一组完整且有效的配置：

1. 命令行临时覆盖
2. `<skill-dir>/api-image.toml`
3. `OPENAI_IMAGE_API_KEY` + `OPENAI_IMAGE_BASE_URL`
4. `OPENAI_API_KEY` + `OPENAI_BASE_URL`
5. Codex 根目录的 `auth.json` + `config.toml`

每个优先级代表一个完整的服务商身份，不得跨层拼接 API 密钥和 URL。更高层命中后忽略所有更低层；高层配置出错时直接停止，不回退。

### 3.3 `api-image.toml`

文件支持三个字段：

```toml
base_url = "https://provider.example.com/v1"
# api_key = "<API 密钥>"
api_key_env = "API_IMAGE_API_KEY"
```

密钥选择顺序：

1. `api_key` 有非空值时直接使用。
2. `api_key` 为空或未提供时，使用 `api_key_env` 作为环境变量名，再读取该变量的值。
3. 两个密钥字段都为空时，跳过此配置层并继续下一级。

补充规则：

- `base_url` 必须是 `http://` 或 `https://`，并与密钥来自同一配置层。
- 配置了密钥字段但缺少 `base_url` 时，立即报错。
- 已配置 `api_key_env` 但对应环境变量为空或未设置时，立即报错。
- `base_url`、`api_key`、`api_key_env` 全部为空时，视为禁用此层。
- 不建议把真实密钥写入 TOML；优先使用 `api_key_env`。

设置环境变量示例：

```powershell
$env:API_IMAGE_API_KEY = "<API 密钥>"
```

### 3.4 环境变量和 Codex 根目录

图像专用环境变量必须成对出现：

```powershell
$env:OPENAI_IMAGE_API_KEY = "<API 密钥>"
$env:OPENAI_IMAGE_BASE_URL = "https://provider.example.com/v1"
```

通用环境变量也必须成对出现：

```powershell
$env:OPENAI_API_KEY = "<API 密钥>"
$env:OPENAI_BASE_URL = "https://provider.example.com/v1"
```

未命中上述配置时：

- 从 `auth.json` 读取 `OPENAI_API_KEY`。
- 从 `config.toml` 读取 `model_provider`，再读取对应 `[model_providers.<name>].base_url`。
- 任一必需字段缺失、为空或类型错误都必须报错。

不得默认补入 OpenAI 官方 URL，也不得从不同来源拼出不完整配对。

## 4. 任务路由

### 4.1 模式

- 仅有文字提示词：`generate`。
- 有任意 `--image` 或 `--mask`：`edit`。
- `--mode auto` 时按上述规则自动判断。
- `--mode edit` 没有 `--image` 必须报错。
- `generate` 模式不得携带 `--image` 或 `--mask`。

### 4.2 端点

| 任务 | 端点 | 请求格式 |
| --- | --- | --- |
| 文生图 | `<base_url>/images/generations` | JSON |
| 参考图、编辑、蒙版、合成 | `<base_url>/images/edits` | `multipart/form-data` |

默认模型为 `gpt-image-2`；只有服务商要求其他模型时才使用 `--model` 覆盖。

### 4.3 输入图像角色

每张输入图像都要明确角色，可使用 `--image-role` 附加到提示词：

- `编辑目标`
- `风格参考`
- `构图参考`
- `身份参考`
- `产品参考`
- `地形参考`
- `蒙版`
- `合成来源`

有蒙版时，第一个 `--image` 必须是编辑目标；其他图像只能作为参考或合成来源。蒙版约束是需要验证的目标，不承诺像素级不变。

## 5. 研究与参考资料

### 5.1 需要研究的主题

对以下主题默认先研究：真实地点、建筑、桥梁、产品、车辆、机器、用户界面、制服、文化服饰、历史场景、生物、地图、技术图表、当前状态或小众艺术风格。

研究目的：确认结构、比例、材料、地形、功能、颜色、周围环境和相机角度等事实，避免生成泛化或错误结果。

### 5.2 参考图策略

- 视觉结构、轮廓、比例、材料或地形需要准确时，优先寻找并下载至少一张参考图。
- 可使用多张互补参考图，分别承担主体结构、环境地形或构图角度等角色。
- 参考图应传给脚本并标注角色，不得把所有图像都当作编辑目标。
- 参考图生成应要求模型创作新图，不得完全复制源照片。
- 若无法访问网络或参考图，应明确说明准确性受限；不得假装已完成研究。
- 服务商拒绝参考图编辑请求时，直接报告错误；只有用户接受时才讨论纯文本后备方案，不得静默回退。

### 5.3 研究结果进入提示词

只加入与任务相关的事实。不得凭空添加人物、道具、品牌、标志、故事或其他用户未要求的细节。

## 6. 提示词规范

提示词应尽量包含以下信息：

```text
用途：<photorealistic-natural|product-mockup|ui-mockup|infographic-diagram|logo-brand|illustration-story|stylized-concept|historical-scene|text-localization|identity-preserve|precise-object-edit|lighting-weather|background-extraction|style-transfer|compositing|sketch-to-render>
资产类型：<使用位置>
主要请求：<用户原始需求>
研究事实/视觉参考：<仅列相关事实和观察>
输入图像：<图像 1：角色；图像 2：角色>
场景/背景：<环境>
主体：<主要主体>
风格/媒介：<照片、插画、3D 等>
构图/取景：<视角、镜头、位置>
光照/氛围：<光照和氛围>
材料/纹理：<表面细节>
文字（逐字）："<需要精确呈现的文字>"
约束：<必须保留或必须修改>
避免：<负面约束>
```

默认使用用户的语言；提示词可包含换行。迭代时一次只改变一个主要因素，便于判断结果差异。

## 7. 命令与参数

### 7.1 单条文生图

```powershell
python "<skill-dir>\\scripts\\generate_image.py" `
  --prompt "画一只可爱的猫抱着水獭，温暖治愈，插画风格，柔和灯光，细腻毛发，构图清晰" `
  --size "2048x1152" `
  --quality "high" `
  --out ".\\outputs\\cute-cat-otter.png"
```

### 7.2 参考图或编辑

```powershell
python "<skill-dir>\\scripts\\generate_image.py" `
  --prompt "参考输入图的构图和角色姿势，生成一张暖色电影感插画" `
  --image "C:\\path\\to\\reference.png" `
  --image-role "构图和姿势参考" `
  --size "2048x2048" `
  --quality "high" `
  --out ".\\outputs\\reference-output.png"
```

### 7.3 局部编辑

```powershell
python "<skill-dir>\\scripts\\generate_image.py" `
  --prompt "只把被蒙版标出的区域替换成一只小水獭，保持其他区域不变" `
  --image "C:\\path\\to\\source.png" `
  --mask "C:\\path\\to\\mask.png" `
  --out ".\\outputs\\masked-edit.png"
```

### 7.4 批量规则

- 默认使用 `--prompt`，即使提示词包含多行或多个段落。
- 已存在的长提示词文件可使用 `--prompt-file`，其全部内容视为一条提示词。
- 只有用户明确要求“批量生成”“逐条生成列表”或“每行作为独立提示词”时，才允许使用 `--prompt-list <path> --batch`。
- `--prompt-list` 必须与 `--batch` 同时使用；不得仅因文本有多行、编号、多个主题或文件名而自行推断批量意图。
- `--prompt`、`--prompt-file`、`--prompt-list` 必须且只能选一个。

### 7.5 常用参数

| 参数 | 说明 |
| --- | --- |
| `--model` | 默认 `gpt-image-2` |
| `--mode` | `auto`、`generate`、`edit` |
| `--size` | 默认 `2048x1152`；也可用 `auto` |
| `--quality` | `low`、`medium`、`high`、`auto`；默认 `high` |
| `--n` | 每条提示词生成 1 至 10 张；默认 1 |
| `--image` | 可重复，最多 16 张，每张不超过 50 MB |
| `--image-role` | 可重复，数量不得超过 `--image` |
| `--mask` | 局部编辑蒙版 |
| `--background` | `auto`、`opaque`、`transparent` |
| `--output-format` | `png`、`jpeg`、`webp` |
| `--output-compression` | 0 至 100，仅适用于 `jpeg` 或 `webp` |
| `--input-fidelity` | `low` 或 `high`；`gpt-image-2` 不支持 |
| `--moderation` | `auto` 或 `low` |
| `--codex-home` | 覆盖 Codex 根目录 |
| `--timeout` | 默认 1800 秒；`0` 表示不设客户端超时 |
| `--out` | 输出路径；显式指定 `--output-format` 时自动匹配扩展名，缺省时生成带时间戳的文件名 |

## 8. 配置临时覆盖

临时覆盖必须同时提供 URL 和 API 密钥，并且每类参数只能选一种来源：

- URL：`--base-url` 或 `--base-url-env <ENV_NAME>`
- 密钥：`--api-key` 或 `--api-key-env <ENV_NAME>`

优先使用 `--api-key-env`，仅在用户明确提供一次性密钥并接受命令行暴露风险时使用 `--api-key`。

```powershell
$env:JOB_IMAGE_API_KEY = "<临时 API 密钥>"
python "<skill-dir>\\scripts\\generate_image.py" `
  --prompt "一张赛博朋克风格的夜景照片" `
  --base-url "https://provider.example.com/v1" `
  --api-key-env "JOB_IMAGE_API_KEY" `
  --out ".\\outputs\\temporary-provider.png"
```

临时覆盖只对本次运行有效，不得写回 `api-image.toml`、`auth.json` 或 `config.toml`。缺少 URL 或密钥中的任一项时，必须在网络请求前报错。

## 9. 请求与响应

### 9.1 `generations` JSON

```json
{
  "model": "gpt-image-2",
  "prompt": "你的中文或英文提示词",
  "size": "2048x1152",
  "quality": "high",
  "n": 1
}
```

### 9.2 `edits` multipart

```text
model=gpt-image-2
prompt=<编辑或参考提示词>
image[]=@source-or-reference.png
mask=@mask.png
size=1024x1024
quality=high
n=1
```

输入图像使用重复的 `image[]` 字段。第一个输入图像是编辑目标时，蒙版必须与它格式、尺寸一致并包含 Alpha 通道。

响应解析顺序：

1. 优先解码 `data[].b64_json`。
2. 对非官方 OpenAI 兼容服务商或旧版模型，才将 `data[].url` 作为后备并下载图像。
3. 缺少可解码图像数据时直接报错。

## 10. 模型与输入校验

### 10.1 尺寸

显式尺寸必须满足：

- 宽和高都是 16 的倍数。
- 最长边不超过 3840 像素。
- 长宽比不超过 3:1。
- 总像素数在 655,360 至 8,294,400 之间。

常用有效尺寸：`1024x1024`、`1536x1024`、`1024x1536`、`2048x2048`、`2048x1152`、`3840x2160`、`2160x3840`。不合法时必须报错，不得静默调整。

### 10.2 `gpt-image-2` 专属限制

- `gpt-image-2` 当前支持透明背景；该能力处于 `preview`，使用 `background: transparent` 时输出格式必须是 `png` 或 `webp`。
- 不得传入 `input_fidelity`；该模型始终以高保真度处理图像输入。
- 蒙版必须与第一个编辑目标格式、尺寸一致，且包含 Alpha 通道。
- 其他模型是否支持透明背景、`input_fidelity` 或 `moderation`，以服务商能力为准；透明背景同时受输出格式限制。

### 10.3 输入文件

- `--image` 最多 16 个文件，每个不超过 50 MB。
- 输入路径必须存在且为普通文件。
- 仅支持可识别的 `PNG`、`JPEG`、`WebP`；无法检查格式或尺寸时必须报错。

## 11. 等待、输出与验证

- 脚本为同步流程；服务商完成任务或返回明确错误前不会退出。
- 默认客户端超时为 1800 秒；长任务应使用更长超时或 `--timeout 0`，调用方不得使用过短的 shell 超时。
- 输出目录会自动创建，脚本向标准输出打印每个最终绝对路径。
- 单张结果使用指定文件名；显式指定 `--output-format` 时自动匹配扩展名。多个变体追加 `-v1`、`-v2`；多条提示词追加 `-p1`、`-p2`；两者同时存在时使用 `-pN-vN`。
- 保存后检查文件确实可读，并依据用户提示词、研究事实、输入图像角色和必须保留的约束进行验证。
- 使用网络研究时，最终回复应包含输出绝对路径、最终提示词和所用来源；不得包含 API 密钥。

## 12. 失败处理

在发起请求前，以下情况必须明确报错并停止：

- 服务商配置不完整、字段类型错误、URL 不是 `http://` 或 `https://`。
- `api_key_env` 指向的环境变量为空或未设置。
- 命令行临时覆盖缺少 URL 或密钥，或同时指定直接值和环境变量来源。
- 未找到任何有效服务商配置；不得默认使用官方 URL。
- `--prompt`、`--prompt-file`、`--prompt-list` 使用错误，或批量模式未获得明确授权。
- 编辑模式缺少 `--image`，或生成模式携带输入图像或蒙版。
- 输入图像、蒙版格式、尺寸、Alpha 通道或文件大小不符合要求。
- `--size`、`--quality`、`--background`、`--output-format`、`--output-compression`、`--input-fidelity`、`--moderation` 或 `--n` 不符合限制。
- 服务商响应缺少 `data[].b64_json` 或可下载的 `data[].url`。

服务商返回的错误应在完成 API 密钥、`Bearer` 凭据和常见 URL 敏感参数脱敏后呈现给用户；过长响应应截断。不得伪造成功、吞掉错误或在错误后静默切换服务商。

## 13. 随附资源

- `api-image.toml`：命令行覆盖之后的最高优先级持久化服务商配置；`api_key` 优先于 `api_key_env`。
- `scripts/generate_image.py`：解析参数、读取配置、构建请求、调用图像端点并保存结果。
- `scripts/provider_imagegen/`：配置解析、参数校验、请求编码、响应解码和输出处理模块。
