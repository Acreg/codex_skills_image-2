# 模型、质量、尺寸与预设

仅在用户询问模型、显式指定模型、需要精确参数或 API 返回参数错误时读取。

## 模型与请求提示

| 模型 ID | 特征与定位 | 优点 | 缺点 | 默认质量 | 透明底 |
|---|---|---|---|---|---|
| `gpt-image-2.5-flare` | 2.5 快速版；日常、草图、批量、一般编辑 | 延迟较低，迭代效率高 | 极复杂构图、文字和微细节通常弱于 Sunburst | `medium` | PNG/WebP；验证真实 Alpha |
| `gpt-image-2.5-sunburst` | 2.5 高质量版；复杂构图、密集细节、文字、最终成品 | 成品细节、材质和构图表现更强 | 通常等待更久 | `high` | PNG/WebP；验证真实 Alpha |
| `gpt-image-2.5` | 用户主动选择的 2.5 通用模型名 | 质量与速度相对均衡 | 无后缀模型可能未被当前账号池或分组开放 | `medium` | 支持透明参数；验证路由与 Alpha |
| `gpt-image-2` | 旧接口兼容模型 | 兼容渠道覆盖通常更广 | 质量、速度或新能力通常不如 2.5 系列 | `medium` | PNG/WebP；验证真实 Alpha |
| `gpt-image-2-2026-04-21` | GPT Image 2 固定快照 | 输出行为更稳定，便于复现 | 不自动获得后续模型改进 | `medium` | 支持透明参数；验证真实 Alpha |

模型显示优先级固定为：用户显式模型 > preset 模型 > 默认模型 `gpt-image-2.5-flare`。开始提示和 30 秒进度播报使用请求提交时确定的模型 ID：

```text
图片生成请求已发送，使用模型{MODEL_ID}正在绘图中，请稍后
图片生成进度：使用模型{MODEL_ID}，已等待{SECONDS}秒，当前状态：{OBSERVED_STATUS}
```

这里的 `{MODEL_ID}` 是请求模型，不需要等待响应中的 `model` 字段，也不能把未验证的响应值说成实际响应模型。

## 质量兼容

| preset | 模型 | 质量 | 用途 |
|---|---|---|---|
| `auto` | Flare | medium | 默认请求 |
| `fast` | Flare | medium | 快速草图 |
| `final` | Sunburst | high | 最终成品 |
| `text-heavy` | Sunburst | high | 海报和准确文字 |
| `benchmark-t2i` | Sunburst | high | 用户未给主题的实际生图测试 |

命令行显式 `--model/--quality/--size/--prompt` 覆盖 preset。

## 尺寸

默认 `auto`。用户明确要求时使用 API 当前支持的 `1024x1024`、`1536x1024` 或 `1024x1536`；比例主要通过用户要求和提示词保持。

## 透明背景

- OpenAI 图片生成文档明确支持 `gpt-image-2.5-flare` 与 `gpt-image-2.5-sunburst` 的透明背景；用户显式选择哪个 2.5 模型就保留哪个，不降级为 `gpt-image-2`。
- `background=transparent` 是请求顶层字段，不是只写在提示词里的描述；透明背景只配合 `output_format=png` 或 `output_format=webp`，不要发送 JPEG。
- Flare 快速透明图：`--model gpt-image-2.5-flare --background transparent --output-format png`。
- Sunburst 高质量透明图：`--model gpt-image-2.5-sunburst --background transparent --output-format png`。
- 第三方中转可能过滤字段或把结果转成 RGB；必须检查返回的请求模型、`image_mode`、`bands`、`has_alpha`、`alpha_min` 和 `alpha_max`。验收至少要求 PNG/WebP、Alpha 通道且 `alpha_min<255`；否则按透明交付失败处理，不自动换模型重发。

## Gemini Nano Banana 2.1

本 Skill 另外支持 gemini-nano-banana-2.1，通过 Sub2API /v1beta/models/gemini-nano-banana-2.1:generateContent 转发，而非 OpenAI Images。可设置 aspectRatio、imageSize (1K/2K/4K)、thinkingLevel、Google Search、imageOnly 与重复参考图。--output-format 是本地转码。详见 [Gemini Native](gemini-v1beta.md)。
