# 配置和安装

安装包内所有路径均相对包目录或由当前系统环境计算。Python 3.11+：运行包内 `image-image-generation-portable/install.py`；其他客户端可用 `--skills-dir <该客户端的技能目录>`。Windows 双击包根目录 `安装图片Skill.cmd`；macOS/Linux 运行 `sh image-image-generation-portable/install-codex.sh`。升级保留已有 `.env` 和独立配置。

## 自动路由

GPT 请求由脚本判断当前客户端。Codex 非 API 登录返回 `native_required`，交由内置生图工具；Codex API 模式从当前 CODEX_HOME 的 provider 与对应凭据读取配对的 URL/Key，支持 `experimental_bearer_token`、provider `env_key` 或 `auth.json`；仅允许 HTTPS 的 `*.onemini.top`。读取失败如实报错，不拿其他用户、旧配置或 `.env` 拼凑。其他客户端只用技能目录 `.env` 的 GPT 配置，默认 Onemini URL，不读取 Codex 凭据。

```dotenv
OPENAI_API_KEY = ""
OPENAI_BASE_URL = "https://api.onemini.top/v1"
GEMINI_API_KEY = ""
GEMINI_BASE_URL = "https://api.onemini.top/v1beta"
```

Gemini 必须使用独立 Key：到 api.onemini.top 新建 **gemini-cli 渠道分组**的 Key，填入 `GEMINI_API_KEY`。不要复用 GPT Key、在聊天回显或把 `.env` 打包上传。历史 Gemini 独立配置仍保留。`.env` 是本地明文，请保护文件权限。

## 缺失依赖

图片保存和验证依赖 Pillow。若缺少，先询问用户是否同意安装；同意后使用当前 Python 执行 `python -m pip install Pillow`。若 Python 本身缺失，同样先询问，再按用户平台安装 Python 3.11+。不要在正常生图前主动联网检查依赖或更新。

## 更新

用户要求更新时阅读 [更新说明](updates.md)，从维护仓库获取发布包并保留本地配置；不自动重发可能已计费的生图请求。
