# GPT-image2图片生成工具 · Codex 便携安装包

版本：4.0.2。内部调用名 **aa-onemini-image-generation**，安装目录为 **image-image-generation**，Codex 显示名 **GPT-image2图片生成工具**。

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



