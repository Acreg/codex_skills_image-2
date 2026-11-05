# 模型、质量、尺寸与 GIF

默认 `gpt-image-2.6`，本版只支持此无后缀 2.6 ID；同时保留 `gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`、`gpt-image-2.5`、`gpt-image-2`、`gpt-image-2-2026-04-21` 和 `gemini-nano-banana-2.1`。用户显式模型 > preset 模型 > 默认模型。`fast` 为 2.6/medium，`final` 和 `text-heavy` 为 2.6/high。旧版 2.5 模型仍可显式选择。

静态图可用 `--size 3840x2160` 等实际通道支持的尺寸；返回元数据给出实际宽高。透明 PNG/WebP 使用 `--background transparent` 并验证 Alpha。

## GIF

```text
<python> -B <技能目录>/scripts/generate_image.py run --output-format gif --prompt "循环摇尾巴的狐狸"
<python> -B <技能目录>/scripts/generate_image.py run --output-format gif --frame-count 15 --frame-duration-ms 200 --prompt "循环摇尾巴的狐狸"
```

只支持 `gpt-image-2.6` 文生图；本版本 GIF 不支持 `--size`，请求体不发送 size。未明确要求时也不发送帧数和时长，让上游决定。上游或中转可能忽略显式帧参数，脚本保留原始 GIF 并返回实际 `width`、`height`、`frame_count`、`frame_durations_ms` 和 `duration_ms`。不符时状态为 `partial`，应交付原始文件并解释差异，不拉伸、不补帧、不自动重试。

Nano Banana 使用独立 `GEMINI_API_KEY`；详见 [Gemini](gemini-v1beta.md)。
