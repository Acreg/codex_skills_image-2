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

Codex API 模式自动读取当前 provider 的 Onemini URL 与对应 Key；Codex 非 API 登录返回 `native_required`，使用原生工具。非 Codex 客户端读取技能目录 `.env`。详见 [配置](configuration.md)。正常请求不运行 `config-check`；只有错误后才按需诊断。历史 `--config-source fallback` 仅用于非 Codex 客户端兼容，不能用于绕过 Codex 的 Onemini 域名限制。

## 运行环境

- 使用当前项目作为工作目录，不进入技能安装目录执行。
- Codex Desktop 可使用 bundled Python；其他环境使用 Python 3.11+ 与 Pillow。
- 缺少依赖时先询问用户意见；同意后用当前 Python 安装 Pillow，不在正常请求前探测或安装。
- API 调用可能按所选渠道单独计费；超时或结果未知时先检查已有输出，不重复发送。

## Gemini Nano Banana 2.1

运行 python scripts/generate_image.py list-models 真实查询 GET /v1beta/models；选定 gemini-nano-banana-2.1 后，run 和 edit 走 Gemini generateContent。详见 [Gemini Native](gemini-v1beta.md)。
