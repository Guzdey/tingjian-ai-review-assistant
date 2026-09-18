from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from .config import Settings
from .schemas import NeedParseRequest, ParsedNeed


class ModelClientError(RuntimeError):
    """A safe, user-displayable model integration error."""


class QwenClient:
    """Small DashScope OpenAI-compatible client with no SDK dependency."""

    def __init__(self, settings: Settings) -> None:
        if not settings.dashscope_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required")
        self._settings = settings

    def _chat_json(self, *, model: str, system: str, user: str) -> dict[str, Any]:
        endpoint = self._settings.qwen_base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self._settings.request_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ModelClientError(f"模型服务返回 HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise ModelClientError("模型服务当前不可达或响应超时") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelClientError("模型服务返回了无法解析的响应") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("模型响应缺少 choices[0].message.content") from exc
        if not isinstance(content, str):
            raise ModelClientError("模型响应内容不是 JSON 文本")
        content = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if fenced:
            content = fenced.group(1)
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ModelClientError("模型未返回合法 JSON") from exc
        if not isinstance(decoded, dict):
            raise ModelClientError("模型 JSON 根节点必须是对象")
        return decoded

    def parse_need(self, request: NeedParseRequest) -> ParsedNeed:
        schema_hint = {
            "raw_text": request.text,
            "scenes": ["commute|meeting|exercise|long_wear|general"],
            "aspects": [
                {
                    "name": "noise_cancellation|call_quality|connection|comfort|battery|sound_quality",
                    "priority": "integer 1..3",
                }
            ],
            "constraints": [{"code": "snake_case", "label": "简短中文", "hard": True}],
        }
        payload = self._chat_json(
            model=self._settings.qwen_parse_model,
            system=(
                "你是需求结构化组件。只能输出 JSON，不做商品推荐。"
                "严格使用给定枚举；不确定时少填，不要编造约束。"
            ),
            user=json.dumps(
                {
                    "task": "把用户的耳机使用需求解析为固定结构",
                    "input": request.model_dump(mode="json"),
                    "required_shape": schema_hint,
                },
                ensure_ascii=False,
            ),
        )
        payload["raw_text"] = request.text
        try:
            need = ParsedNeed.model_validate(payload)
        except ValidationError as exc:
            raise ModelClientError("模型需求解析结果未通过结构校验") from exc

        scenes = list(need.scenes)
        for scene in request.selected_scenes:
            if scene not in scenes:
                scenes.append(scene)
        aspect_by_name = {item.name: item for item in need.aspects}
        for aspect in request.selected_aspects:
            if aspect not in aspect_by_name:
                from .schemas import AspectPreference

                aspect_by_name[aspect] = AspectPreference(name=aspect, priority=3)
        return need.model_copy(
            update={"scenes": scenes[:5], "aspects": list(aspect_by_name.values())[:6]}
        )

    def generate_report_copy(
        self,
        *,
        user_need: dict[str, Any],
        product: dict[str, Any],
        aspect_results: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        allowed_citation_ids: set[str],
    ) -> dict[str, Any]:
        payload = self._chat_json(
            model=self._settings.qwen_report_model,
            system=(
                "你是有证据约束的耳机评论报告编辑器。只能使用输入中的统计与证据，"
                "不得补充商品参数、价格、品牌或常识。每项具体结论必须能由 citation_ids 中的证据支持。"
                "只输出 JSON。"
            ),
            user=json.dumps(
                {
                    "task": "生成简洁中文报告文案",
                    "need": user_need,
                    "product": product,
                    "aspect_results": aspect_results,
                    "evidence": evidence,
                    "required_shape": {
                        "summary": "1..400字",
                        "advantages": ["每项1..180字，最多6项"],
                        "risks": ["每项1..180字，最多6项"],
                        "unknowns": ["每项1..180字，最多6项"],
                        "citation_ids": ["只能从输入证据 id 中选择，最多24个"],
                    },
                },
                ensure_ascii=False,
            ),
        )
        return _validate_report_copy(payload, allowed_citation_ids)


def _text_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) > 6:
        raise ModelClientError(f"模型报告字段 {field} 格式不正确")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not (1 <= len(item.strip()) <= 180):
            raise ModelClientError(f"模型报告字段 {field} 含无效文本")
        result.append(item.strip())
    return result


def _validate_report_copy(payload: dict[str, Any], allowed_ids: set[str]) -> dict[str, Any]:
    summary = payload.get("summary")
    if not isinstance(summary, str) or not (1 <= len(summary.strip()) <= 400):
        raise ModelClientError("模型报告 summary 格式不正确")
    citation_ids = payload.get("citation_ids")
    if not isinstance(citation_ids, list) or len(citation_ids) > 24:
        raise ModelClientError("模型报告 citation_ids 格式不正确")
    if any(not isinstance(item, str) or item not in allowed_ids for item in citation_ids):
        raise ModelClientError("模型报告包含不存在的引用编号")
    if len(citation_ids) != len(set(citation_ids)):
        raise ModelClientError("模型报告包含重复引用编号")
    return {
        "summary": summary.strip(),
        "advantages": _text_list(payload.get("advantages"), "advantages"),
        "risks": _text_list(payload.get("risks"), "risks"),
        "unknowns": _text_list(payload.get("unknowns"), "unknowns"),
        "citation_ids": citation_ids,
    }
