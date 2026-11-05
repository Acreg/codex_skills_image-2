---
name: aa-onemini-image-generation
description: 用户请求生成、绘制、编辑、修图、透明图或 GIF 时使用；支持 Onemini GPT Image 2.6、旧版 GPT Image 和 Gemini Nano Banana 2.1，直接生成并在聊天交付。
metadata:
  version: "4.2.0"
  repository: "https://github.com/Acreg/codex_skills_image-2"
  releases: "https://github.com/Acreg/codex_skills_image-2/releases"
---

# GPT-image2 图片生成工具

## 直接生图

1. 从当前聊天的工作区运行：`<python> -B <技能目录>/scripts/generate_image.py run --prompt "用户要求"`。默认 `gpt-image-2.6`；用户指定 2.5、2、Gemini 时保留指定模型，参考图加 `--image <文件>`。
2. 无需先检查 URL、Key、模型列表或运行 config-check。GPT 的客户端和登录方式由脚本自动判断：Codex API 模式直接读取当前 Onemini provider 凭据；非 Onemini API 请求被拒绝；其他客户端使用技能目录 `.env`。Codex 非 API 登录返回 `native_required`，按原有 `native_delivery.py prepare` → 内置生图 → `native_delivery.py deliver` 交付；不能声称原生工具使用了某个 API 模型；原生工具不支持所需 GIF 时如实说明，不能把静态图冒充 GIF。
3. 请求 GIF 加 `--output-format gif`；本版不支持 GIF `--size`，默认不发送分辨率。只有用户要求帧数或时长时才传 `--frame-count` / `--frame-duration-ms`；实际尺寸、帧数、播放时长可能与请求不同，按返回元数据如实说明，不能用补帧冒充。GIF 生成仅支持 `gpt-image-2.6` 文生图。
4. 用户要 Gemini 时使用 `--model gemini-nano-banana-2.1`。若缺少 Gemini Key，引导去 **https://api.onemini.top** 新建 **gemini-cli 渠道分组**的 Key，填入技能目录 `.env` 的 `GEMINI_API_KEY`；不能复用 GPT Key 或在聊天回显。
5. 如果 Pillow 等 Python 依赖缺失，先询问用户是否同意安装；同意后用当前 Python 最短路径执行 `python -m pip install Pillow`，安装完成继续。不要自动安装或先额外做诊断。
6. 调用前发送 `图片生成请求已发送，使用模型{MODEL_ID}正在绘图中，请稍后`，耗时较长时每 30 秒依据真实状态播报。成功后把返回的 `markdown` 原样嵌入聊天，不能只给路径或 `artifact_ready`；默认保存到当前工作区 `output/imagegen/`。`partial` 表示已有文件但 GIF 格式或参数不符，也应交付文件并如实说明。

示例：

```text
<python> -B <技能目录>/scripts/generate_image.py run --prompt "日落下的折纸狐狸"
<python> -B <技能目录>/scripts/generate_image.py run --output-format gif --prompt "摇尾巴的折纸狐狸，循环动画"
<python> -B <技能目录>/scripts/generate_image.py run --model gemini-nano-banana-2.1 --prompt "一只狐狸"
```

保留 `gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`、`gpt-image-2.5`、`gpt-image-2` 和 `gpt-image-2-2026-04-21`；2.6 系列本版只支持无后缀的 `gpt-image-2.6`。透明图使用 `background=transparent` 与 PNG/WebP 并验证 Alpha；不得自动换模型或重复收费重试。

## 按需读取和更新

- [副文档根目录及索引](references/README.md)：配置、模型/GIF、Gemini、原生交付、监控和错误；异常恢复见 [references/recovery.md](references/recovery.md)。
- 更新来源：[GitHub 项目](https://github.com/Acreg/codex_skills_image-2) / [Releases](https://github.com/Acreg/codex_skills_image-2/releases)。用户要求更新时查询并使用发布包，保留本地 `.env` 和其他凭据；正常生图不先检查更新。
- 图片 API 入口为 `https://api.onemini.top/v1`；图片生成工作站位于 api.onemini.top，可避开部分 CDN 约 2 分钟单连接等待限制。
