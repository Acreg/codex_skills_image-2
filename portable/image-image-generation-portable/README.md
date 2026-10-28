# GPT-image2图片生成工具 · Codex 便携安装包

版本：4.1.3。内部调用名 **aa-onemini-image-generation**，安装目录为 **image-image-generation**，Codex 显示名 **GPT-image2图片生成工具**。

## 一键安装

可把整个解压文件夹 **image-image-generation-portable** 放在当前用户的 **.codex** 目录中，直接从该文件夹运行安装入口：

- Windows：解压完整 Release ZIP 后优先双击根目录 **安装图片Skill.cmd**；只有本便携目录时双击 **install-codex.cmd**
- macOS / Linux：运行 **sh ./install-codex.sh**
- 通用命令行：Python 3.11+，运行 **python install.py**

脚本会读取 **CODEX_HOME**，未设置时使用当前用户的 **~/.codex/skills/**。如果只有 **~/.agents/skills/image-image-generation** 存在，会更新原有位置，不再创建重复目录。

旧版本会自动备份到相同 skills 父目录下的 **.image-skill-backups/**；同版本内容一致直接跳过。安装全过程离线进行，不访问图片 API，不读取密钥，也不产生图片生成费用。安装时自动创建 .env 空白模板，更新时保留用户填写的 .env。安装后重新启动 Codex 即可使用。

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

## 根目录 .env 配置（v4.1.3）

安装后将看到 image-image-generation/.env（与 SKILL.md 同级）。
直接用记事本、VS Code 或智能体编辑即可，**不必运行 PowerShell 环境变量命令**。

    OPENAI_API_KEY = ""
    OPENAI_BASE_URL = ""

    GEMINI_API_KEY = ""
    GEMINI_BASE_URL = "https://api.onemini.top/v1beta"

GPT Image 两项留空，默认读取当前 Codex 的 auth.json（GPT Key）和 config.toml（Base URL）。
如果要换成其他 GPT Key，在 .env 显式填入即可。
Gemini 需要填写独立的 GEMINI_API_KEY；不会窃取或借用 GPT Key，也支持另一 API 地址。
历史 gemini-config.local.json 仍被兼容读取，不强制迁移。升级时 .env 原样保留。

图片生成依旧保存于项目 output/imagegen/，并将实际图片嵌入聊天框；原生图片工具的
prepare、deliver 及精确调用恢复流程不变。


完整 Release 还附带官方 Windows x64 Python 3.14.10 离线 EXE、Pillow cp314 wheel 和安装说明.txt；跨平台使用原便携目录 install-codex.sh。旧版聊天图片交付流程完整保留在 image-image-generation/references/workflow.md。
