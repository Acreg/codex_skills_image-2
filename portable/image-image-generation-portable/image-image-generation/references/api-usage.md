# API 直出与一次性配置

仅在需要精确模型、项目文件，或 `run` 返回配置错误时读取。正常请求不先运行 `config-check`。

## Onemini 端点与图片生成工作站

- API Base URL：`https://api.onemini.top/v1`。
- 文生图：`POST /v1/images/generations`；图生图：`POST /v1/images/edits`。
- 登录 `https://api.onemini.top` 后，可从侧边栏进入“图片生成工作站”。工作站使用任务化生成链路，可绕过 CDN 单次连接约 2 分钟的等待上限；长耗时、高质量和批量生图优先推荐工作站。
- Skill 脚本继续用于 Codex 内直接落盘与聊天交付；不要把站点登录凭证写进 Skill、提示词或日志。

## 快速调用

保持当前项目为工作目录，脚本会直接写入 `output/imagegen/`：

```text
<python> -B <skill-root>/scripts/generate_image.py run --prompt "一只橘猫坐在月球上"
<python> -B <skill-root>/scripts/generate_image.py run --model gpt-image-2.5-sunburst --quality high --prompt "复杂精细海报"
<python> -B <skill-root>/scripts/generate_image.py run --model gpt-image-2.5-flare --background transparent --output-format png --prompt "一只孤立的红熊猫吉祥物，干净边缘，无文字"
<python> -B <skill-root>/scripts/generate_image.py run --model gpt-image-2.5-sunburst --quality high --background transparent --output-format png --prompt "高细节透明吉祥物"
<python> -B <skill-root>/scripts/generate_image.py run --image input/photo.png --prompt "只改变背景"
<python> -B <skill-root>/scripts/generate_image.py run --preset benchmark-t2i
```

`run` 没有 `--image` 时发送文生图，有一个或多个 `--image` 时发送图生图。脚本内部完成参数默认值、配置读取、唯一文件名、图片解码和原子写入；不要先调用 `config-check`。

透明背景参数示例：

```text
<python> -B <skill-root>/scripts/generate_image.py run --model gpt-image-2.5-flare --background transparent --output-format png --prompt "isolated mascot, clean edges, no text"
<python> -B <skill-root>/scripts/generate_image.py run --model gpt-image-2.5-sunburst --quality high --background transparent --output-format webp --prompt "isolated detailed mascot, clean edges, no text"
```

脚本会对 Flare/Sunburst 保留显式模型，在请求体顶层发送 `background: "transparent"` 与所选 `output_format`，并在保存前验证 PNG/WebP 是否包含 Alpha 通道和透明像素。`transparent + jpeg` 会在联网前返回配置错误。

## 配置来源

已有 API 配置按以下顺序读取：

- Key：当前进程 `OPENAI_API_KEY` → 当前机器 Codex `auth.json` 顶层显式 `OPENAI_API_KEY`。
- 地址：`OPENAI_BASE_URL` → 当前机器 `config.toml` 所选 provider 的 `base_url` → 官方 API 默认地址。
- 不读取或转换 OAuth 登录令牌。

缺少显式 Key 时，`run` 会在发送网络请求前返回配置错误。若用户只需要聊天预览，直接改用一次原生图片工具；若用户要求精确模型或项目成品，再进行一次性 API 配置。

`config-check` 仅用于配置或诊断，不属于正常生图流程：

```text
<python> -B <skill-root>/scripts/generate_image.py config-check
```

## 专用配置

安装者明确选择独立配置时，按 [fallback-setup.md](fallback-setup.md) 操作，并显式使用：

```text
<python> -B <skill-root>/scripts/generate_image.py run --config-source fallback --prompt "测试"
```

不把 Key 放入命令行、源码、日志或聊天。更换已有专用配置仍需单独确认；输出图片的 `--force` 不代表配置替换确认。

## 运行环境

- 使用当前项目作为工作目录，不进入技能安装目录执行。
- Codex Desktop 可使用 bundled Python；其他环境使用 Python 3.11+ 与 Pillow。
- 缺少依赖时才处理依赖，不在正常请求前探测或安装。
- API 调用可能按所选渠道单独计费；超时或结果未知时先检查已有输出，不重复发送。

## Gemini Nano Banana 2.1

运行 python scripts/generate_image.py list-models 真实查询 GET /v1beta/models；选定 gemini-nano-banana-2.1 后，run 和 edit 走 Gemini generateContent。详见 [Gemini Native](gemini-v1beta.md)。
