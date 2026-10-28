# Python 3.14.10 Windows x64 离线安装包

本目录存放 Python Software Foundation 发布的原版安装程序。Python 3.14.10 满足当前 Codex 图片生成 Skill 的 Python 3.11+ 要求。

| 文件 | 用途 |
|---|---|
| python-3.14.10-amd64.exe | Windows x64 官方离线安装程序，适用于常见的 64 位 Windows 电脑 |
| LICENSE.python.txt | Python 原版许可证、版权及分发条款 |

## 安装方式

1. 如果电脑上没有可用的 Python 3.11+，双击 python-3.14.10-amd64.exe，在官方安装向导中安装。需要在终端使用 python 命令时，可以选择把 Python 加入 PATH。
2. 打开新的终端，运行 python --version 确认版本。
3. 回到 Codex Skill 安装包目录，双击 install-codex.cmd，即可安装 **GPT-image2图片生成工具**。
4. 如果已有 Python 3.11+，直接跳过 Python 安装步骤。

该 Python 安装程序不会被仓库脚本自动执行，用户需要自行双击运行。

## 来源与验证

- 官方发布页：https://www.python.org/downloads/release/python-31410/
- 官方原文件：https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe
- 版本：3.14.10（2026-10-25）
- 大小：33,498,520 字节
- SHA-256：92480239264744fe0386a1bd8275786fefa126e3129e56a68e22b52c73329965
- Windows Authenticode：Valid，签名者为 Python Software Foundation。
- 这里是未修改的官方程序；Python 及其许可证归原权利人所有。

本包只适用于 **Windows x64**。Windows ARM64、macOS、Linux 请从 Python 官方下载对应平台安装程序。
