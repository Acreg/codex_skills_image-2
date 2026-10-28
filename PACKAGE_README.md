# GPT-image2图片生成工具 · Codex 便携安装包


**配置更新（v4.1.3）：** 安装后 Skill 根目录自动出现 .env，GPT 两项默认留空直接沿用 Codex 的 auth.json/config.toml，Gemini 在同一文件填写专用 Key。旧版将实际图片交付到聊天框的 prepare/deliver + Markdown 图片流程保留。

版本：4.1.3。内部调用名 **aa-onemini-image-generation**，安装目录为 **image-image-generation**，Codex 显示名 **GPT-image2图片生成工具**。

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




## GPT / Gemini 独立密钥

GPT 使用原有 OPENAI_API_KEY、OPENAI_BASE_URL；Nano Banana 使用 GEMINI_API_KEY、GEMINI_BASE_URL
或者本地 gemini-config.local.json（使用 configure-gemini 命令配置）。
两者的 API Key 独立，Gemini 不会回退使用 GPT Key。安装器会保留两种本地配置。

## v4.1.3 安装包变化

完整 ZIP 含 `安装说明.txt`、`安装图片Skill.cmd`、Python 3.14.10 Windows x64 官方安装程序，以及 Pillow cp314 离线轮子。
用户可直接双击安装，也可把 ZIP 给 Codex 自动安装。
根目录 `.env` 首次安装生成、升级保留；GPT 默认读取 Codex 原有 auth.json/config.toml。
聊天实际图片嵌入规则保存在主 SKILL.md 快速入口和 references/workflow.md 详细流程中。
