# 详细图片生成、监控和聊天交付流程（原版规则存档）

---
name: aa-onemini-image-generation
description: 用户要求生成、绘制、设计、编辑、修图，或询问 GPT-image2图片生成工具 如何使用时使用；支持 Onemini API、GPT Image 2/2.5、Gemini Nano Banana 2.1、透明 PNG/WebP、项目落盘和聊天图片交付。
metadata:
  version: "4.1.2"
  repository: "https://github.com/Acreg/codex_skills_image-2"
  releases: "https://github.com/Acreg/codex_skills_image-2/releases"
---

# GPT-image2图片生成工具

## 强制触发

只要用户请求生成、绘制、设计、编辑、修图、透明背景图片、Logo、海报或其他图片，第一动作必须调用图片生成工具。不得先输出分析、方案或确认问题，也不得在没有调用工具时声称已生成图片。

本 Skill 将“生成结果”和“聊天交付”视为两个独立状态：

- `session` 只保存本次精确调用的恢复源，不是最终交付位置；
- 项目 `output/imagegen/` 保存可复用的持久化产物；
- 当前最终回复必须包含真实图片附件，或嵌入本次产物返回的 Markdown 图片；
- 工具返回 `completed`、出现工具卡片、生成了缩略图占位符、文件已落盘，都不能单独证明用户在聊天框看到了图片。

## 简单使用说明

用户询问“这个 Skill 怎么使用”时，优先用下面的简短信息回答，不展开安装和排错细节：

- 直接描述要生成或修改的图片，并可指定模型、质量、尺寸、透明背景及输出格式；未指定模型时默认使用快速版 `gpt-image-2.5-flare`。
- Onemini API Base URL：`https://api.onemini.top/v1`；文生图使用 `/v1/images/generations`，图生图使用 `/v1/images/edits`。
- 登录 `https://api.onemini.top` 后，侧边栏提供“图片生成工作站”。工作站采用任务化生成链路，可绕过 CDN 单次连接约 2 分钟的生图等待上限；长耗时、高质量或批量生图优先推荐在那里完成。
- Codex 内使用时，Skill 会把成品保存到当前项目 `output/imagegen/` 并把真实图片嵌入聊天。

### 模型速览

| 模型 | 特征 | 优点 | 缺点 | 透明底 |
|---|---|---|---|---|
| `gpt-image-2.5-flare` | 2.5 快速版，默认 `medium` | 响应快，适合日常、草图、批量 | 极复杂构图和细节通常弱于 Sunburst | 支持 PNG/WebP，必须验证 Alpha |
| `gpt-image-2.5-sunburst` | 2.5 高质量版，默认 `high` | 细节、复杂构图、文字和成品质量更好 | 通常等待更久 | 支持 PNG/WebP，必须验证 Alpha |
| `gpt-image-2.5` | 2.5 通用模型名 | 质量与速度相对均衡 | 具体账号或分组可能未开放该无后缀模型 | 支持透明参数，实际路由和 Alpha 需验证 |
| `gpt-image-2` | 兼容模型 | 现有兼容链路覆盖较广 | 质量、速度或新能力通常不如 2.5 系列 | 支持 PNG/WebP，必须验证 Alpha |
| `gpt-image-2-2026-04-21` | GPT Image 2 固定快照 | 行为更稳定，便于复现 | 不自动获得后续模型改进 | 支持透明参数，必须验证 Alpha |

完整模型参数见 [references/models.md](references/models.md)，API 示例见 [references/api-usage.md](references/api-usage.md)。

## API Key 自动读取规则（不要要求用户每次打开 PowerShell）

安装后在 Skill 根目录自动生成可手动编辑的 .env 文件，模板是 .env.example。

- **GPT Image 默认沿用 Codex 现有配置**：读取 CODEX_HOME（通常 ~/.codex）下 auth.json 的 OPENAI_API_KEY 和 config.toml 当前 model_provider 的 base_url。只有用户在本 Skill 的 .env 明确填写非空 OPENAI_API_KEY / OPENAI_BASE_URL 时，才覆盖对应字段；环境变量仅保持既有兼容，不要求用户设置。
- **Gemini Nano Banana 使用独立凭据**：优先从 Skill 根目录 .env 的 GEMINI_API_KEY、GEMINI_BASE_URL 读取，不复用 GPT 密钥。旧 gemini-config.local.json 配置仍可兼容读取。缺少 Gemini Key 时提示在 .env 填写。
- .env 的两种模型配置互不混用；初始化时 GPT 字段留空，Gemini URL 预填 https://api.onemini.top/v1beta，Gemini Key 由用户填写。模型可应用户要求协助编辑 .env，但不得把真实 Key 输出到聊天、GitHub 或日志。
- 生图时直接走 generate_image.py run 读取配置并生成，不先进行 list-models 或 config-check，以免拖慢首次出图。
- **旧版聊天图片交付规则不能删除或降级**：原生图片工具使用 prepare、deliver 对本次调用取回实际图片；API 调用返回的 markdown 必须在最终回复中嵌入真实图片，不得只给文件路径。

## 单图强制流程

1. 有输入图片时走图生图/编辑路径；没有输入图片时走文生图路径。需求足够时直接执行，不补问非关键细节。
2. 使用用户明确指定的模型、尺寸、质量、背景、格式和输出位置；未指定时使用脚本默认值。透明背景必须把 `background=transparent` 作为请求字段发送，并使用 `output_format=png` 或 `webp`，不能只写进提示词。
3. API/项目成品路径使用 `scripts/generate_image.py run`，不先运行 `config-check`。未指定输出位置时，默认写入当前项目：

   ```text
   <当前项目根目录>/output/imagegen/<唯一文件名>.png
   ```

   技能目录、session 目录和桌面不是默认项目产物目录。用户明确指定的路径可以作为额外副本，但项目 `output/imagegen/` 仍是聊天交付的规范来源。
4. 普通聊天预览或原生图片工具路径必须在调用前创建项目输出状态：

   ```text
   <当前项目>/output/imagegen/.delivery/<唯一ID>.json
   ```

   然后执行：

   ```text
   py -3.12 -B <技能目录>/scripts/native_delivery.py prepare \
     --state <项目输出状态文件> \
     --out <项目>/output/imagegen/<唯一文件名>.png
   ```

   `prepare` 记录当前任务和调用基线，防止把旧图、其他任务图片或用户截图当成本次结果。
5. 在调用图片工具前确定本次请求模型，解析优先级固定为：用户显式 `--model`/模型选择 > 当前 preset 的模型 > 默认模型 `gpt-image-2.5-flare`。随后紧接图片工具调用前单独发送：

   ```text
   图片生成请求已发送，使用模型{MODEL_ID}正在绘图中，请稍后
   ```

   `{MODEL_ID}` 必须替换为本次请求确定的模型 ID；按用户确认的规则显示请求模型，不额外等待响应中的模型字段。
6. 只调用一次图片生成工具。不要因为预览空白、工具卡片缺失或聊天没有缩略图而重复生成。
7. 原生工具结束后，必须检查当前回复是否真的包含可打开的图片附件。无论附件是否可见，只要已执行 `prepare`，都必须对本次精确调用执行一次：

   ```text
   py -3.12 -B <技能目录>/scripts/native_delivery.py deliver \
     --state <项目输出状态文件> \
     --call-id <本次精确 image_generation_call ID>
   ```

   这一步把结果从 session 恢复并写入项目 `output/imagegen/`；它不是重新生图。
8. 读取 `deliver` 或 `generate_image.py run` 返回的 `output`、`markdown`、图片格式、尺寸和 Alpha 字段。最终回复必须直接嵌入返回的 `markdown`，不要手动猜路径、不要只返回路径、不要只说“图片在上方”。
9. 透明背景请求必须确认 PNG/WebP、存在 Alpha 通道且至少有透明像素。图片文件必须可打开，主体和数量必须符合请求。
10. 用户明确指定桌面或其他路径时，先完成项目 `output/imagegen/` 规范交付，再复制到用户指定位置；不要把聊天截图、工具卡片截图或用户上传截图当作生成图片。

## Gemini Nano Banana 2.1

当用户明确选择 gemini-nano-banana-2.1 / Nano Banana 2.1 / 大香蕉，使用脚本 generate_image.py run --model gemini-nano-banana-2.1。文生图及参考图均走 Sub2API 的 POST /v1beta/models/gemini-nano-banana-2.1:generateContent，不走 GPT Image 的 /v1/images 接口。

仅在用户主动查询模型时，使用 generate_image.py list-models 真实请求 GET /v1beta/models；不在每次生成前额外请求。

支持 --aspect-ratio、--image-size（1K/2K/4K）、--thinking-level（minimal/medium/high）、--google-search、--image-only 以及重复 --image 参考图。Gemini 不接受 OpenAI 独有的 quality、size 和 background 参数。--output-format 仅在本地转换图片格式，不能宣称上游支持透明底或输出格式指定。

Gemini 优先读取 Skill 根目录 .env 的 GEMINI_API_KEY / GEMINI_BASE_URL，也兼容 configure-gemini 保存的旧独立 Key；没有 Gemini Key 则如实报错，绝不回退使用 GPT 的 OPENAI_API_KEY。若没有单独指定地址，可沿用现有 Codex 服务商主机，再切换 /v1 到 /v1beta。Sub2API Gemini 分组、模型白名单及允许图片生成规则仍按服务器实际配置生效。不需要额外开发解锁开关。返回图片读取 candidates[].content.parts[].inlineData，含多图时全部保存，真实图片交付后完成。

详细请求示例：[Gemini Native](references/gemini-v1beta.md)。

## GPT Image 2.5 透明背景

用户明确选择 `gpt-image-2.5-flare` 或 `gpt-image-2.5-sunburst` 并要求透明背景时，保留该模型，不降级或替换为 `gpt-image-2`。使用 API/项目成品路径发送顶层字段 `background=transparent`，输出格式只能为 PNG 或 WebP：

```text
<python> -B <技能目录>/scripts/generate_image.py run \
  --model gpt-image-2.5-flare \
  --background transparent --output-format png \
  --prompt "孤立主体，干净边缘，无背景"
```

高质量版将模型替换为 `gpt-image-2.5-sunburst`。生成后必须验证返回的请求模型、PNG/WebP、`has_alpha=true` 且 `alpha_min<255`；若中转或上游忽略透明字段并返回 RGB/全不透明图片，按失败处理，保留证据且不自动换模型重发。详细参数见 [references/models.md](references/models.md)。

## 聊天交付门禁

只有同时满足以下条件，才允许结束本轮：

1. 本次精确图片调用有明确结果；
2. 没有未处理的风控拒绝、HTTP 错误或连接断开；
3. 真实图片已经验证并保存到当前项目 `output/imagegen/`，或用户明确指定的项目内路径；
4. 当前最终回复已经出现真实图片附件，或已经嵌入本次返回的 Markdown 图片；
5. 透明背景请求已验证真实 Alpha 通道和透明像素。

下列状态都不是完成状态：`completed`、`artifact_ready`、`CHAT_RENDER_UNVERIFIED`、本地文件已保存、工具调用卡片出现、只返回 JSON、只返回路径、只写“已生成”。

如果原生附件不可见，必须执行 `native_delivery.py deliver`；如果当前回复仍没有可见附件，也必须把 `deliver` 返回的 `markdown` 原样放入最终回复。只有把真实图片交付内容放入最终回复后，才能结束对话。

## 监测与异常

- 请求提交后从 0 秒开始计时，每 30 秒固定检查并播报一次本次精确调用；即使状态没有变化也必须播报，不能使用“仅状态变化才播报”替代。
- 进度格式固定为：

  ```text
  图片生成进度：使用模型{MODEL_ID}，已等待{SECONDS}秒，当前状态：{OBSERVED_STATUS}
  ```

- `{OBSERVED_STATUS}` 只能来自本次精确调用、正在运行的进程或对应会话记录；没有真实百分比时使用“等待上游响应”等可验证状态，不虚构百分比或完成度。
- 完成、明确失败、连接被动断开或调用结束后立即停止 30 秒播报；不得因为等待时间变长而主动取消、终止、制造超时或放弃请求。
- 发生错误时立即停止监测，并输出错误码/类别、脱敏后的原始报错、准确中文翻译和解决建议；固定格式见 [references/errors.md](references/errors.md)。

  ```text
  图片生成失败
  使用模型：{MODEL_ID}
  错误码/类别：{HTTP_STATUS_OR_UPSTREAM_CODE} / {CATEGORY}
  原始报错（脱敏后）：{RAW_ERROR}
  中文翻译：{TRANSLATION}
  解决建议：{SUGGESTION}
  ```
- 风控拒绝必须原样转告，不自动改写提示词、绕过风控或重试。
- 502、503 和其他 HTTP 错误必须报告实际错误码和上游原始信息，不把未知结果说成成功。
- 发生被动断开或附件、项目文件同时缺失时，才按 [references/recovery.md](references/recovery.md) 使用当前任务和精确调用 ID恢复；不得选择“最新图片”，不得读取其他任务，不得把恢复当作生成、不得重复生图。

## 更新与维护

- 技能维护仓库：[codex_skills_image-2](https://github.com/Acreg/codex_skills_image-2)
- 版本发布与更新下载：[GitHub Releases](https://github.com/Acreg/codex_skills_image-2/releases)
- 只有用户确认更新后才执行升级；检查、安装和回滚流程见 [references/updates.md](references/updates.md)。

## 按需读取

- 模型、质量、尺寸、背景、输出格式与预设：[references/models.md](references/models.md)
- Gemini Nano Banana 2.1：[references/gemini-v1beta.md](references/gemini-v1beta.md)
- 提示词与固定测试内容：[references/prompting.md](references/prompting.md)
- 项目落盘、原生交付与聊天嵌入：[references/delivery.md](references/delivery.md)
- 原生图片兼容入口：[references/native-delivery.md](references/native-delivery.md)
- 监测、风控、HTTP 与 Cloudflare：[references/monitoring.md](references/monitoring.md)
- 图片实际缺失后的精确恢复：[references/recovery.md](references/recovery.md)
- API 命令、首次配置与环境：[references/api-usage.md](references/api-usage.md)
- 多图并发与请求绑定：[references/parallel.md](references/parallel.md)
- 错误分类：[references/errors.md](references/errors.md)
- 失败后的更新检查：[references/updates.md](references/updates.md)
