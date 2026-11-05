# GPT-image2 图片生成工具 v4.2.0

跨电脑安装包使用相对路径；Python 3.11+。Windows 解压后双击包根目录 `安装图片Skill.cmd`，macOS/Linux 运行 `sh image-image-generation-portable/install-codex.sh`。也可执行 `python image-image-generation-portable/install.py --skills-dir <客户端技能目录>` 安装到其他客户端。安装默认读取当前 CODEX_HOME，或使用当前用户的 `.codex/skills`；升级保留本地 `.env` 和独立配置。

默认模型 `gpt-image-2.6`，支持 GIF（不传分辨率），保留旧 GPT Image 及 Gemini。Codex API 模式自动读取当前 Onemini provider；其他客户端在技能目录 `.env` 配置 API Key。Gemini 请到 api.onemini.top 新建 gemini-cli 渠道分组 Key，单独填写 `GEMINI_API_KEY`。生成结果保存当前工作区 `output/imagegen/` 并嵌入聊天。

缺少 Python 或 Pillow 时先询问用户；同意后按安装说明操作。安装器本身不调用生图 API。

维护仓库：https://github.com/Acreg/codex_skills_image-2
