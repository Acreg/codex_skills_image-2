# 原生图片交付兼容入口

本文件保留旧链接兼容，但正常单图也必须遵循项目落盘和聊天交付门禁。

- 默认输出：当前项目 `output/imagegen/`，不要只保存在 session。
- 生图前：`native_delivery.py prepare --state <项目状态文件> --out <项目输出图片>`。省略 `--out` 时，脚本使用当前项目 `output/imagegen/` 的唯一 PNG。
- 生图后：无论原生附件是否显示，都执行 `native_delivery.py deliver --state <状态文件> --call-id <精确调用ID>`。
- 最终回复：嵌入 `deliver` 返回的 `markdown`；不要只报告 `artifact_ready` 或文件路径。
- 缺图恢复：[recovery.md](recovery.md)。
