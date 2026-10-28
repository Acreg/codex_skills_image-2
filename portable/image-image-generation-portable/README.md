# GPT-image2图片生成工具 · Codex 便携安装包

版本：4.1.1。内部调用名 **aa-onemini-image-generation**，安装目录为 **image-image-generation**，Codex 显示名 **GPT-image2图片生成工具**。

## 一键安装

可把整个解压文件夹 **image-image-generation-portable** 放在当前用户的 **.codex** 目录中，直接从该文件夹运行安装入口：

- Windows：双击 **install-codex.cmd**
- macOS / Linux：运行 **sh ./install-codex.sh**
- 通用命令行：Python 3.11+，运行 **python install.py**

脚本会读取 **CODEX_HOME**，未设置时使用当前用户的 **~/.codex/skills/**。如果只有 **~/.agents/skills/image-image-generation** 存在，会更新原有位置，不再创建重复目录。

旧版本会自动备份到相同 skills 父目录下的 **.image-skill-backups/**；同版本内容一致直接跳过。安装全过程离线进行，不访问图片 API，不读取密钥，也不产生图片生成费用。安装后重新启动 Codex 即可使用。

需要预先验证安装包时，运行 **python install.py --check**。

## 使用

- 在 Codex 中直接描述要生成或修改的图片，并可选择模型、质量、尺寸、透明背景、PNG/WebP。
- Onemini API Base URL：https://api.onemini.top/v1；文生图接口 /v1/images/generations，图生图 /v1/images/edits。
- 登录 https://api.onemini.top 后，侧边栏的图片生成工作站支持任务式生图。
- Codex 内生成的图片默认保存到当前项目 **output/imagegen/**，并嵌入聊天交付。

## 模型

- gpt-image-2.5-flare：快速版，适合日常、草图、批量；支持透明 PNG/WebP。
- gpt-image-2.5-sunburst：高质量版，适合复杂构图、文字和最终成品。
- gpt-image-2.5：通用模型名，是否开放取决于上游账号分组。
- gpt-image-2：兼容模型。
- gpt-image-2-2026-04-21：固定快照。

透明背景必须设置 background=transparent 与 PNG/WebP，并检查真实 Alpha 通道。

维护仓库：https://github.com/Acreg/codex_skills_image-2

本包不包含用户密钥、会话、生成图片、专用配置或缓存。





## Gemini Nano Banana 2.1

新增 gemini-nano-banana-2.1，通过 Sub2API /v1beta/models 查询真实模型，使用 /v1beta/models/gemini-nano-banana-2.1:generateContent 生图，原有 GPT Image 功能不变。详细用法见 image-image-generation/references/gemini-v1beta.md。

图片生成时需要 Pillow>=10；若 Python 尚未安装 Pillow，按 Skill requirements.txt 安装即可（python -m pip install "Pillow>=10"）。安装器本身离线，不会自动下载依赖。

## GPT 与 Gemini 不同密钥

GPT Image 保持原来的 OPENAI_API_KEY 和 OPENAI_BASE_URL 或 Codex auth.json / config.toml；
Gemini 使用 GEMINI_API_KEY 和 GEMINI_BASE_URL，或者专用本地配置
image-image-generation/gemini-config.local.json。Gemini 不会使用 GPT 的 Key。

可以将 Gemini Key 和地址作为环境变量传入：

    GEMINI_API_KEY=<你自己的 Gemini 或 Sub2API Key>
    GEMINI_BASE_URL=https://api.onemini.top/v1beta

也可以使用 configure-gemini 命令从标准输入保存 JSON，避免把 Key 放在命令行参数中：

    python image-image-generation/scripts/generate_image.py configure-gemini

标准输入 JSON 形如：{"api_key":"<你的 Gemini Key>","base_url":"https://api.onemini.top/v1beta"}。
已经保存的本地 Gemini 和 GPT 配置都会在升级中保留。使用 list-models 实际查询 Gemini /v1beta/models，不需要先配置 GPT Key。
