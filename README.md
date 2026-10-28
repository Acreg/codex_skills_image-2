# Codex 图片生成 Skill：GPT-image2图片生成工具

使用兼容 API 或中转 API 的 Codex 调用 Onemini 图片生成接口。Skill 内部名为 **aa-onemini-image-generation**，安装目录名为 **image-image-generation**。

## 一键安装（跨电脑，无固定路径）

从 [GitHub Releases](https://github.com/Acreg/codex_skills_image-2/releases/latest) 下载 **aa-onemini-image-generation-v4.0.2-portable.zip**（不要下载 GitHub 自动生成的 Source code 包）。解压后可把整个 **image-image-generation-portable** 文件夹放入当前用户的 **.codex** 目录，并从解压文件夹启动脚本。

| 平台 | 操作 |
|---|---|
| Windows | 双击 **install-codex.cmd** |
| macOS / Linux | 在解压目录运行 **sh ./install-codex.sh** |
| 通用命令行 | Python 3.11+，运行 **python install.py** |

无需填写安装路径。脚本从自身所在目录获取完整 Skill，按环境变量 **CODEX_HOME** 定位用户的 Codex 目录；未设置时使用当前用户的 **~/.codex/skills/**。如果同名 Skill 只存在于 **~/.agents/skills/**，会就地更新以避免重复。

已安装则自动更新并将旧版备份在同目录的 **.image-skill-backups/**；内容完全相同则跳过。安装仅使用本地文件，不调用图片 API，也不读取密钥。

Windows 示例位置（仅为示例，不写死在脚本中）：**%USERPROFILE%\.codex\image-image-generation-portable\install-codex.cmd**。

完成后重新启动 Codex，在对话框输入斜杠 **/** 查找 **GPT-image2图片生成工具**。

## 使用

在 Codex 中描述要生成的图片并指定模型、质量、尺寸和透明背景即可，或通过 **/** 选择 Skill。支持 GPT Image 2 / 2.5、透明 PNG/WebP，默认保存至当前项目的 **output/imagegen/**。

![Codex Skill 选择界面](https://github.com/user-attachments/assets/c1ebfc58-ceb8-4121-95d2-9971afe3fcbb)

![图片生成示例](https://github.com/user-attachments/assets/d22c2969-50cd-46f5-a354-8599474a8eae)

## 验证与维护

- **python install.py --check**：离线校验，不修改安装位置。
- **python install.py --skills-dir PATH**：指定另一个 skills 父目录。
- 需要 Python 3.11+；Windows 优先使用可正常启动的 Python 3.11+，macOS/Linux 优先使用 python3。
- 旧版备份保留在安装目录的父目录 **.image-skill-backups/**。需要回退时关闭 Codex 后自行恢复。
- 如果 **.codex/skills** 和 **.agents/skills** 都已有同名 Skill，优先更新前者，不擅自删除另一份。

仓库提供与 Release 一致的安装入口源码；图片生成主体位于 Release 便携包中。




## 本分支附带的 Python 离线安装程序

本分支提供 [Python 3.14.10 Windows x64 离线安装程序](python-installers/windows-x64/python-3.14.10-amd64.exe)，适合尚未安装 Python 3.11+ 的 Windows 电脑。安装前请阅读 [使用说明和 SHA-256 校验值](python-installers/windows-x64/README.md)。

Python 安装与 Codex Skill 安装是两项独立操作；已有 Python 3.11+ 的电脑无需重复安装。
