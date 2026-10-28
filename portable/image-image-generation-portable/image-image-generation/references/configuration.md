# Skill 配置和安装

## 自动 / 手动安装

- 从项目 GitHub Release 下载完整 ZIP 并解压，Windows 双击解压根目录 `安装图片Skill.cmd`，或运行 `image-image-generation-portable/install-codex.cmd`。
- Windows x64 没有 Python 3.11+ 时，先双击 `python-installers/windows-x64/python-3.14.10-amd64.exe` 安装官方 Python。ZIP 根目录附有 `安装说明.txt`。
- Codex 智能体可根据用户指定的 ZIP 路径解压并执行 `image-image-generation-portable/install.py`，自动安装到当前 CODEX_HOME 下，不需要问用户安装位置。旧版本及用户 .env 会保留。
- macOS/Linux 使用 `sh image-image-generation-portable/install-codex.sh`，使用平台现有 Python 3.11+。
- 完整项目：https://github.com/Acreg/codex_skills_image-2

## Skill 根目录的 .env

安装时自动生成与 SKILL.md 同级的 .env（明文、本地文件，不上传 GitHub），内容如下：

```dotenv
OPENAI_API_KEY = ""
OPENAI_BASE_URL = ""

GEMINI_API_KEY = ""
GEMINI_BASE_URL = "https://api.onemini.top/v1beta"
```

- GPT 两项默认留空：默认读当前 Codex 的 `auth.json` 中 OPENAI_API_KEY 与 `config.toml` 当前 model_provider 的 base_url；如明确需要，可在 .env 单独覆盖。
- Gemini 填自己的 Key，不能使用 GPT Key；Gemini URL 可指定另一服务器。
- 模型可在用户请求下编辑 .env，不应在聊天或 GitHub 中泄露密钥。无需配置 PowerShell 环境变量。
- 兼容旧 gemini-config.local.json；更新时 .env 原样保留。
- 多用户 Windows 下要确认当前实际 CODEX_HOME，避免把 A 用户的 Skill 改在 B 用户目录。

## 聊天交付不变

图片默认保存当前项目 `output/imagegen/`。工具输出的真实 Markdown 图片必须直接嵌入最终回复；Codex 原生图片工具继续执行原版 prepare/deliver 精确恢复，不得只报路径。详见 [`workflow.md`](workflow.md)。
