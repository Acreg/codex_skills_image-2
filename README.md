# Codex 图片生成 Skill：GPT-image2图片生成工具

## Gemini Nano Banana 2.1 新版下载（当前开发分支）

本分支可直接使用 [GPT-image2-gemini-nano-banana-2.1-v4.1.0-preview.zip](dist/GPT-image2-gemini-nano-banana-2.1-v4.1.0-preview.zip)。**解压后进入 image-image-generation-portable 目录，运行其中的 install-codex.cmd（Windows）或 sh ./install-codex.sh（macOS/Linux）**。

新功能支持 Sub2API GET /v1beta/models 和 POST /v1beta/models/gemini-nano-banana-2.1:generateContent。可查看 [Gemini 参数与用法](portable/image-image-generation-portable/image-image-generation/references/gemini-v1beta.md)。

Windows x64 电脑如缺少 Python 3.11+，本分支亦保留 [Python 3.14.10 官方离线安装程序](python-installers/windows-x64/python-3.14.10-amd64.exe)。安装脚本不会自动执行 Python EXE。

注意：下文原有 Latest Release 链接仍指向已发布的 v4.0.2 GPT Image 稳定版；**想试用 Gemini 必须下载上面的 v4.1.0 预览包**。本分支尚未在生产 Sub2API 使用付费 Key 验收。


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




## Gemini Nano Banana 2.1 开发分支

本分支支持 gemini-nano-banana-2.1 的 Sub2API Gemini 原生 /v1beta 模型列表和 generateContent 图片链路。安装包完整源码位于 portable/image-image-generation-portable；可在其中双击 install-codex.cmd 或使用 python install.py。详见该目录 image-image-generation/references/gemini-v1beta.md。

该分支仅在本地使用合成图像和环回测试服务验收，尚未用真实 API Key 触发在线收费生成。
