# 图片实际缺失后的恢复

本文件只用于异常情况。恢复不是生成、重试或正常项目保存。

## 触发条件

正常原生路径应在生成前 prepare、生成后 deliver。恢复文档只处理 prepare 缺失、状态损坏或 deliver 未找到本次结果的异常情况。必须同时满足：

1. 当前图片调用已经结束；
2. 聊天中没有可见图片；
3. 项目中没有本次输出文件；
4. 结果不是明确失败或内容拒绝。

`completed` 不能跳过缺图检查；`artifact_ready` 表示本地文件已保存，不应再次恢复或生成。不满足恢复条件时直接使用已有附件或文件，不读取会话。

## 有 prepare 状态

```text
<python> -B <skill-root>/scripts/native_delivery.py deliver --state <本次.delivery.json>
```

## 没有 prepare 状态

只有当前任务会话文件和本次 `image_generation_call` ID 都已明确时使用：

```text
<python> -B <skill-root>/scripts/generate_image.py recover-native --session-file <当前任务.jsonl> --call-id <本次调用ID> --out <绝对输出.png>
```

恢复只读取当前任务和精确调用，不选择“最新图片”，不重新发送图片请求。至多做一次短暂只读复查；仍无数据时报告具体状态并结束。
