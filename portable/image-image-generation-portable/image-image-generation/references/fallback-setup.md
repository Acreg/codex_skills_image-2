# 安装者专用配置（可选）

原生工具不需要独立 API Key。只有用户明确要求使用独立 API 时才配置；不要为了安装测试读取认证文件或发送请求。

## 安全输入

请安装者选择 HTTPS API 根地址。通用版默认官方 API 地址，兼容第三方地址由安装者自己指定；不要求使用特定商家、分组或菜单。

Key 通过用户本机隐藏输入，不粘贴进聊天或命令行。保存文件为技能目录下 `fallback-config.local.json`，采用明文保存；共享整个已配置的技能目录会泄露凭证。告知这一风险，不能声称隐藏输入等于加密存储。

保持项目目录为工作目录，将下方 `<skill-root>` 替换为实际技能目录，再使用选定的 Python 3.11+ 运行下面的 Python 代码（交互终端，不使用会记录输入的网页聊天）：

```python
import getpass
import json
from pathlib import Path
import subprocess
import sys

script = (Path("<skill-root>") / "scripts" / "generate_image.py").resolve()
url = input("HTTPS API 地址（留空使用官方 API）：").strip()
payload = {"api_key": getpass.getpass("API Key（输入不回显）：")}
if url:
    payload["base_url"] = url
subprocess.run(
    [sys.executable, str(script), "configure-fallback"],
    input=json.dumps(payload), text=True, check=True,
)
```

没有可供用户隐藏输入的交互终端时先停止配置，并给出本机操作步骤；不要改成向聊天索要 Key。现有配置不会默认覆盖，用户确认替换后才加入 `--replace-config`。此步骤只做本地格式校验，不验证接口、不发生成请求。

配置与调用相互独立；调用前说明可能单独计费并取得授权。调用时显式选择 `--config-source fallback`。不要把 Key 写入日志、示例、测试或安装包。打包只使用公开文件白名单。
