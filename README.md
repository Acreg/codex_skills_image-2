# Onemini 生图 Skill

## 给智能体：最快安装

1. 下载 [最新 Release](https://github.com/Acreg/codex_skills_image-2/releases/latest) 中的便携 ZIP，解压到当前工作区。
2. 在解压目录运行（使用 Python 3.11+；macOS/Linux 可用 `python3`）：

   ```text
   python -B image-image-generation-portable/install.py
   ```

   如果已经在本仓库根目录，直接运行 `python -B portable/image-image-generation-portable/install.py`，无需下载 ZIP。非 Codex 客户端在上述命令后追加 `--skills-dir <该客户端的技能目录>`。
3. 从安装器输出的 `target` 打开 `SKILL.md`，报告安装完成；必要时新开会话刷新技能列表。升级会保留技能目录内的 `.env` 和独立配置。

安装不需要读取或询问密钥，也不要为验证发起收费生图。之后用户要求生图时，按 `SKILL.md` 直接调用；Codex 自动选择原生工具或 Onemini API，其他客户端按提示配置技能目录的 `.env`。Gemini 使用在 api.onemini.top 的 **gemini-cli 渠道分组**中新建的独立 Key。不要在聊天、日志或仓库中暴露 Key。

若运行所需 Python 或 Pillow 缺失，先询问用户是否同意安装；同意后使用当前 Python 的 pip 最短路径安装，再继续。
