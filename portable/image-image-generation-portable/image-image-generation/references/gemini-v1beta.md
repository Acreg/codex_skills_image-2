# Gemini Nano Banana 2.1 / Sub2API v1beta

首版支持的 Gemini 模型 ID：gemini-nano-banana-2.1。

## 最快配置方式：Skill 根目录 .env

安装脚本会在 Skill 根目录生成 .env（不上传 GitHub）。用编辑器直接填写：

    OPENAI_API_KEY = ""
    OPENAI_BASE_URL = ""

    GEMINI_API_KEY = "你的 Gemini Key"
    GEMINI_BASE_URL = "https://api.onemini.top/v1beta"

GPT 留空时沿用 ~/.codex/auth.json 和 ~/.codex/config.toml 的原始凭据。
Gemini 只使用自己的 Key；不需要用户在 PowerShell 设置环境变量，也无需每次生成前查询模型列表。
本 Skill 也允许用户在 .env 显式填写独立 GPT Key 和主机，以覆盖 Codex 默认配置。
历史 gemini-config.local.json 仍兼容，若 .env 没有指定 Gemini Key，使用该文件。
图片生成后必须继续执行聊天图片嵌入流程，不能仅输出文件链接。

## 接口与认证

- 模型列表：GET /v1beta/models，真实列出 Sub2API 所返回的模型；命令：python scripts/generate_image.py list-models
- 生图：POST /v1beta/models/gemini-nano-banana-2.1:generateContent
- **Gemini 专用凭据**：优先使用 Skill 根目录 .env 中的 GEMINI_API_KEY / GEMINI_BASE_URL。没有对应配置时兼容读取
  image-image-generation/gemini-config.local.json（由 configure-gemini 从标准输入写入）；
  Gemini 不读取或复用 GPT 的 OPENAI_API_KEY / auth.json 凭据。
- 两种协议可分别使用不同的 Sub2API Key，甚至不同的 API 提供商主机。
  如果没有单独指定 Gemini 地址，才会优先复用 Codex 配置的主机地址，但密钥仍然分离。
- Gemini 使用 Authorization: Bearer <Gemini Key>；GPT 使用 Authorization: Bearer <GPT Key>。
- 例：Codex Base URL 为 https://api.onemini.top/v1 时自动使用 https://api.onemini.top/v1beta。
- Sub2API 的 Key 分组必须具备 Gemini 图片生成权限，并有可调度的模型或映射。
- 请求图片在 contents[0].parts[].inlineData；返回图片取 candidates[0].content.parts[].inlineData。

## 生图

使用命令：

    python scripts/generate_image.py run --model gemini-nano-banana-2.1 --prompt "夜景城市街道摄影" --aspect-ratio 16:9 --image-size 2K

参考图编辑：

    python scripts/generate_image.py run --model gemini-nano-banana-2.1 --prompt "参照此图修改天空" --image ./reference.jpg --thinking-level high --output-format png

原生请求示例：

    {
      "contents": [{"role": "user", "parts": [{"text": "夜景城市街道摄影"}]}],
      "generationConfig": {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": {"aspectRatio": "16:9", "imageSize": "2K"}
      }
    }

## 可用参数

| 命令参数 | 对应 Gemini REST 字段 |
|---|---|
| --aspect-ratio 16:9 | generationConfig.imageConfig.aspectRatio |
| --image-size 2K | generationConfig.imageConfig.imageSize，1K/2K/4K |
| --thinking-level high | generationConfig.thinkingConfig.thinkingLevel，minimal/medium/high |
| --image-only | generationConfig.responseModalities = [IMAGE]，否则 TEXT+IMAGE |
| --google-search | tools[].googleSearch |
| --image ./reference.jpg，可重复 | contents[0].parts[].inlineData |
| --output-format png/jpeg/webp | 本地 Pillow 转码；不会发送给 Gemini 上游 |

宽高比可选：1:1、1:4、1:8、2:3、3:2、3:4、4:1、4:3、4:5、5:4、8:1、9:16、16:9、21:9。

Gemini 不支持 GPT Image 专用 --quality、--size、--background 参数映射；不承诺透明底。服务端可返回文字、思考或多个图片 part；工具保存实际图片，错误不自动重试。

## 源码依据

Sub2API：backend/internal/server/routes/gateway.go、backend/internal/handler/gemini_v1beta_handler.go、backend/internal/service/gemini_messages_compat_service.go、backend/internal/service/gemini_image_output_accounting.go。

Google Gemini 原生 API 官方：https://ai.google.dev/api/generate-content

图片生成 API 文档：https://ai.google.dev/gemini-api/docs/generate-content/image-generation

本地离线测试不使用生产 API Key。真实 Sub2API 生图尚未执行，需要单独验收。
