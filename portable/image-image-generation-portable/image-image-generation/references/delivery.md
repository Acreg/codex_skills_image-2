# 图片落盘与聊天交付

## 规范产物位置

- 未指定输出位置时，API 和原生路径都必须把真实图片保存到当前项目的 `output/imagegen/`，使用唯一文件名。
- 用户明确指定桌面或其他位置时，项目 `output/imagegen/` 仍保留规范副本；用户指定路径作为额外副本。
- `session` 中的 `image_generation_call.result` 只用于当前任务的精确恢复，不作为唯一落盘位置。
- 不得把技能目录、聊天截图、工具卡片截图或用户上传截图当作生成产物。

## API 路径

```text
generate_image.py run
→ 写入当前项目 output/imagegen/<unique>
→ 验证图片可读、格式、尺寸和 Alpha
→ 读取返回的 output 与 markdown
→ 将 markdown 原样嵌入最终回复
```

脚本返回的 `delivery_required=true` 是硬要求。不能只打印 JSON、路径或“已生成”。

## 原生路径

```text
选择项目 output/imagegen/<unique>.png 和 .delivery/<unique>.json
→ native_delivery.py prepare
→ 只调用一次原生图片工具
→ 检查当前回复是否真的有图片附件
→ 无论附件可见与否，native_delivery.py deliver --call-id <精确调用ID>
→ 验证项目文件
→ 把 deliver 返回的 markdown 原样嵌入最终回复
```

`deliver` 返回 `artifact_ready/CHAT_RENDER_UNVERIFIED` 时，表示本地产物已验证保存、聊天渲染尚未确认；这时仍必须把返回的 `markdown` 放入当前回复。`completed`、工具卡片或缩略图占位符不是聊天交付证明。

## 交付验证

- 普通图片：确认文件可打开、主体和数量符合请求。
- 透明背景：确认 PNG/WebP、存在 Alpha 通道且有透明像素。
- 最终回复必须包含真实图片附件或本次产物返回的 Markdown 图片；只写路径不算交付。
