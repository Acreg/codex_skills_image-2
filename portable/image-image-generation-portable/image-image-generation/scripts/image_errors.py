"""Small, secret-safe error reports shared by the image skill CLI."""
from __future__ import annotations

import json
import re
from typing import Any

# HTTP meanings are diagnostic possibilities, not proof of the upstream cause.
HTTP_GUIDANCE = {
    400: ("request_error", "请求参数、JSON、字段或模型参数可能错误", "按上游具体字段提示修正请求后再试"),
    401: ("authentication_error", "API Key 缺失、无效或认证方式不符", "检查当前地址对应的 Key，不要在日志中输出 Key"),
    403: ("permission_error", "权限、分组、IP 限制或上游拒绝；不能仅凭 403 判断额度不足", "核对模型分组及服务端明确返回的限制"),
    404: ("not_found", "请求路径、接口、模型或资源可能不存在", "核对 API 根地址、接口路径及模型名称"),
    413: ("payload_too_large", "请求体过大，可能是上传图片体积过大", "先减少图片体积或数量；仅涉及上下文时再缩短上下文"),
    429: ("rate_limit", "请求频率、并发或配额限制", "区分限流和额度耗尽；按 Retry-After（如有）等待，不自动重发"),
    502: ("upstream_error", "网关或上游服务异常", "稍后重试前先确认本次是否已生成或计费"),
    503: ("service_unavailable", "服务资源、账号或路由可能不可用", "检查服务状态；仅有具体证据时排查客户端节点配置"),
    504: ("timeout", "网关等待上游处理超时，本次结果可能未知", "先检查已有产物和调用记录，避免重复计费"),
    524: ("timeout", "状态码 524，尚无足够证据确认来自 Cloudflare", "核对代理链路和已有产物，不自动重发"),
}


def redact(text: Any, secrets: tuple[str, ...] = ()) -> str:
    value = str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)Bearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?i)\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
    # Remove credential fields, URL userinfo and query strings (including signed URLs).
    value = re.sub(r'''(?i)(["']?(?:api[_-]?key|authorization|access_token|token|password|cookie|set-cookie)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}]+)''', r'\1[REDACTED]', value)
    value = re.sub(r"(https?://)[^\s/@]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"(https?://[^\s?\"'<>]+)\?[^\s\"'<>]*", r"\1?[REDACTED]", value)
    return value


class SkillError(RuntimeError):
    def __init__(self, message: str, *, category: str = "unknown_error", http_status: int | None = None,
                 cause: str = "尚不能确认原因", action: str = "核对配置与脱敏后的上游说明，不自动重试",
                 outcome: str = "unknown", secrets: tuple[str, ...] = ()):
        self.report = {
            "category": category, "http_status": http_status,
            "upstream_message": redact(message, secrets)[:800],
            "possible_cause": cause, "suggested_action": action,
            "outcome": outcome, "automatic_retry": False,
        }
        super().__init__(json.dumps(self.report, ensure_ascii=False))


class ConfigError(SkillError):
    def __init__(self, message: str):
        super().__init__(message, category="configuration_error", cause="本地配置、依赖或命令参数不完整/无效",
                         action="修正本地配置；保存配置不代表接口已经验证", outcome="not_sent")


class ApiError(SkillError):
    pass


def upstream_error(payload: Any, status: int = 200, headers: Any = None,
                   secrets: tuple[str, ...] = ()) -> ApiError | None:
    """Prefer explicit upstream codes. Safety rejection must never trigger provider switching."""
    obj = payload if isinstance(payload, dict) else {}
    raw_error = obj.get("error")
    detail = raw_error if isinstance(raw_error, dict) else obj
    code = str(detail.get("code") or detail.get("type") or obj.get("code") or "").lower()
    message = detail.get("message") or (raw_error if isinstance(raw_error, str) else "") or obj.get("message") or ""
    refusal = obj.get("refusal") or detail.get("refusal")
    # Support Responses refusal content as well as the Images error object.
    for item in obj.get("output", []) if isinstance(obj.get("output"), list) else []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if isinstance(content, dict) and content.get("type") == "refusal":
                refusal = content.get("refusal") or content.get("text") or "上游明确拒绝生成"
    if isinstance(payload, str):
        message = payload
    text = str(message or refusal or "上游未提供具体错误说明")
    safety = code in {"content_policy_violation", "content_policy_error", "safety_violation", "moderation_blocked", "safety_system", "content_filter", "image_generation_user_error"} and (
        code != "image_generation_user_error" or bool(re.search(r"policy|safety|moderation|规范|违规", text, re.I)))
    safety = safety or bool(refusal) or bool(re.search(
        r"content[_ ]policy[_ ]violation|violat\w*.{0,40}(?:policy|policies)|safety system|moderation.{0,25}(?:blocked|rejected)|(?:图像|图片|内容).{0,30}(?:违反|违规)|违反.{0,12}(?:规范|政策)|内容安全.{0,12}(?:拒绝|拦截)", text, re.I))
    quota = code in {"insufficient_quota", "quota_exceeded", "insufficient_balance", "billing_hard_limit_reached"} or bool(re.search(r"额度不足|余额不足|额度.{0,8}(?:耗尽|用尽)|insufficient.{0,8}(?:quota|balance)|quota.{0,12}exceeded", text, re.I))
    bad_code = code not in {"", "0", "200", "ok", "success"}
    business_error = bool(raw_error) or obj.get("success") is False or obj.get("status") in ("failed", "error", "incomplete") or bad_code
    if status < 400 and not (business_error or safety):
        return None
    category, cause, action = HTTP_GUIDANCE.get(status, (
        "business_error" if status < 400 else "unknown_error", "上游返回业务错误或未知错误", "根据具体上游说明排查，不自动切换接口或重试"))
    outcome = "unknown" if status >= 500 or status < 400 else "failed"
    if status == 524:
        evidence = str(headers or "") + " " + text
        if re.search(r"cloudflare|cf-ray", evidence, re.I):
            cause = "Cloudflare 已连接源站，但等待源站响应或写入请求等过程超时"
    if quota:
        category, cause, action = "quota_exceeded", "上游明确返回额度或余额限制", "核对该 Key 的额度与计费状态，等待或充值不能保证立即可用"
    if safety:
        category, cause, action = "content_policy_rejection", "上游内容安全规则拒绝了本次请求", "请用户调整不合规内容；停止所有模式切换，不自动改写提示词或重试"
        outcome = "failed"
    if "<html" in text.lower() or "<!doctype" in text.lower():
        text = "上游返回 HTML 错误页，已省略页面内容"
    return ApiError(text, category=category, http_status=status, cause=cause, action=action, outcome=outcome, secrets=secrets)
