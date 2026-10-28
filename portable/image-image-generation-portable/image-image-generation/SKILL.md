---
name: aa-onemini-image-generation
description: 用户要绘图、生成图像、编辑图片、海报或 Logo 时立即调用本工具；支持 GPT Image 2/2.5 和 Gemini Nano Banana 2.1；优先最快出图并把真实图片嵌入 Codex 聊天框。
metadata:
  version: "4.1.3"
  repository: "https://github.com/Acreg/codex_skills_image-2"
  releases: "https://github.com/Acreg/codex_skills_image-2/releases"
---

# GPT-image2图片生成工具

## 第一优先级：马上开始生图，并把图片发到聊天

用户请求生成、绘制、编辑、修图、透明背景或海报时，**先执行工具，不先查询模型、不先 config-check、不反复确认**。

1. **选择模型**：未指定默认 `gpt-image-2.5-flare`（快速），精修 `gpt-image-2.5-sunburst`；也支持 `gpt-image-2.5`、`gpt-image-2`、`gpt-image-2-2026-04-21`。用户要大香蕉/Nano Banana 用 `gemini-nano-banana-2.1`。
2. **发起真实生成**：执行 `<python> -B <技能目录>/scripts/generate_image.py run --model <模型> --prompt "<要求>"`。有参考图加 `--image <文件>`。默认成品保存项目 `output/imagegen/`。
3. **凭据自动读取**：GPT 默认读当前 Codex 的 `auth.json`（Key）与 `config.toml`（Base URL）；根目录 `.env` 中只有非空 OPENAI_API_KEY / OPENAI_BASE_URL 才覆盖。Gemini 只读自己的 GEMINI_API_KEY / GEMINI_BASE_URL 或历史 Gemini 独立配置，绝不复用 GPT Key。无需 PowerShell 设置变量。
4. **聊天中直接显示真实图片**：API 工具返回的 `markdown` 必须直接嵌入最终回复，不能仅发路径、JSON、工具卡片或“已生成”。使用 Codex 原生图像工具时严格执行旧版 `native_delivery.py prepare → 生成 → native_delivery.py deliver`，把 `deliver` 返回的 Markdown 图片原样插入聊天；不能因缩略图缺失重复生图。
5. 调用前确认模型，然后发送 `图片生成请求已发送，使用模型{MODEL_ID}正在绘图中，请稍后`；生成时间较长时按 `references/monitoring.md` 每 30 秒从真实状态播报。

最快 GPT 调用：

```text
<python> -B <技能目录>/scripts/generate_image.py run --prompt "你的绘图要求"
```

Nano Banana：

```text
<python> -B <技能目录>/scripts/generate_image.py run --model gemini-nano-banana-2.1 --prompt "你的绘图要求" --aspect-ratio 16:9 --image-size 2K
```

透明底（必须发送 background=transparent，不能降级 GPT Image 2.5 模型，必须验证 Alpha）：

```text
<python> -B <技能目录>/scripts/generate_image.py run --model gpt-image-2.5-flare --background transparent --output-format png --prompt "无背景的主体"
```

**必须实际把图片发到聊天框**：`completed`、`artifact_ready`、已保存文件都不代表用户看到图片；原生 `prepare/deliver` 以及 GPT Image 原版交付流程不得删除。

## 副文档按需读取（不要为首次生图增加读取开销）

- 用户要配置 .env、安装或了解凭据：[`references/configuration.md`](references/configuration.md)。
- 完整原版交付细则（聊天图片、`native_delivery.py`、监控、重试与恢复）：[`references/workflow.md`](references/workflow.md)、[`references/native-delivery.md`](references/native-delivery.md)。
- 模型、透明 PNG/WebP、尺寸：[`references/models.md`](references/models.md)。
- Gemini v1beta、参考图、多图与参数：[`references/gemini-v1beta.md`](references/gemini-v1beta.md)。
- 进度和异常中文解释：[`references/monitoring.md`](references/monitoring.md)、[`references/errors.md`](references/errors.md)、[`references/recovery.md`](references/recovery.md)。
- 项目维护：https://github.com/Acreg/codex_skills_image-2，官方 Onemini 入口：https://api.onemini.top/v1，图片生成工作站在 api.onemini.top，可规避普通 CDN 单连接约 2 分钟等待上限。

**实际请求图像时优先生成；仅用户询问安装/配置/扩展参数时再读取副文档。**
