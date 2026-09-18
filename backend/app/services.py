from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from .config import Settings
from .demo_store import EvidenceStore
from .model_client import ModelClientError, QwenClient
from .schemas import (
    Aspect,
    AspectComparisonRow,
    AspectPreference,
    AspectResult,
    CompareRequest,
    CompareResponse,
    Constraint,
    EvidenceItem,
    EvidenceStrength,
    NeedParseRequest,
    NeedParseResponse,
    ParsedNeed,
    ProductComparisonSummary,
    ReportRequest,
    ReportResponse,
    RuntimeMeta,
    RuntimeMode,
    Scene,
    Stance,
    Verdict,
)


ASPECT_LABELS = {
    Aspect.NOISE_CANCELLATION: "降噪",
    Aspect.CALL_QUALITY: "通话",
    Aspect.CONNECTION: "连接",
    Aspect.COMFORT: "舒适度",
    Aspect.BATTERY: "续航",
    Aspect.SOUND_QUALITY: "音质",
}


SCENE_PATTERNS = {
    Scene.COMMUTE: ("通勤", "地铁", "公交", "火车", "飞机", "commute", "subway", "train"),
    Scene.MEETING: ("会议", "开会", "通话", "电话", "网课", "meeting", "call", "zoom"),
    Scene.EXERCISE: ("跑步", "运动", "健身", "骑行", "exercise", "workout", "running"),
    Scene.LONG_WEAR: ("长时间", "久戴", "全天", "一整天", "long wear", "all day"),
}


ASPECT_PATTERNS = {
    Aspect.NOISE_CANCELLATION: ("降噪", "噪音", "吵", "安静", "anc", "noise"),
    Aspect.CALL_QUALITY: ("通话", "麦克风", "对方听", "人声", "会议", "call", "microphone"),
    Aspect.CONNECTION: ("连接", "断连", "掉线", "蓝牙", "切换", "connection", "disconnect"),
    Aspect.COMFORT: ("舒适", "佩戴", "耳朵", "压耳", "掉落", "稳固", "comfort", "fit"),
    Aspect.BATTERY: ("续航", "电量", "充电", "battery", "charge"),
    Aspect.SOUND_QUALITY: ("音质", "低音", "高音", "人声", "音乐", "sound", "bass"),
}


SCENE_DEFAULT_ASPECTS = {
    Scene.COMMUTE: (Aspect.NOISE_CANCELLATION, Aspect.CONNECTION),
    Scene.MEETING: (Aspect.CALL_QUALITY, Aspect.CONNECTION),
    Scene.EXERCISE: (Aspect.COMFORT, Aspect.CONNECTION),
    Scene.LONG_WEAR: (Aspect.COMFORT, Aspect.BATTERY),
    Scene.GENERAL: (Aspect.SOUND_QUALITY,),
}


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def parse_need_locally(request: NeedParseRequest) -> ParsedNeed:
    text = request.text.casefold()
    scenes = list(request.selected_scenes)
    for scene, patterns in SCENE_PATTERNS.items():
        if scene not in scenes and _has_any(text, patterns):
            scenes.append(scene)
    if not scenes:
        scenes.append(Scene.GENERAL)

    priorities: dict[Aspect, int] = {aspect: 3 for aspect in request.selected_aspects}
    for aspect, patterns in ASPECT_PATTERNS.items():
        if _has_any(text, patterns):
            priorities[aspect] = 3
    for scene in scenes:
        for aspect in SCENE_DEFAULT_ASPECTS[scene]:
            priorities.setdefault(aspect, 2)

    constraints: list[Constraint] = []
    constraint_rules = (
        (
            "no_frequent_disconnect",
            r"(不能|不要|不想|最怕|别).{0,8}(断连|掉线|断开)|连接.{0,6}(稳定|别断)",
            "不能频繁断连",
        ),
        (
            "clear_calls_required",
            r"(对方|别人).{0,8}(听清|听得清)|通话.{0,8}(清楚|清晰)",
            "通话时对方需听清",
        ),
        (
            "comfortable_for_long_wear",
            r"(久戴|长时间|全天).{0,8}(舒服|舒适|不痛|不压)|不能.{0,5}(夹耳|压耳|耳痛)",
            "长时间佩戴不能明显不适",
        ),
        (
            "battery_for_full_day",
            r"(续航|电量).{0,8}(一天|全天|持久|耐用)|不能.{0,5}(频繁充电)",
            "续航需覆盖较长使用时段",
        ),
    )
    for code, pattern, label in constraint_rules:
        if re.search(pattern, text):
            constraints.append(Constraint(code=code, label=label, hard=True))

    aspects = [AspectPreference(name=name, priority=priority) for name, priority in priorities.items()]
    return ParsedNeed(
        raw_text=request.text,
        scenes=scenes[:5],
        aspects=aspects[:6],
        constraints=constraints,
    )


def evidence_strength(count: int) -> EvidenceStrength:
    if count < 3:
        return EvidenceStrength.INSUFFICIENT
    if count < 8:
        return EvidenceStrength.WEAK
    if count < 20:
        return EvidenceStrength.MEDIUM
    return EvidenceStrength.STRONG


def aspect_verdict(support: int, oppose: int, total: int) -> Verdict:
    if total < 3:
        return Verdict.UNAVAILABLE
    if support >= oppose + 2:
        return Verdict.GOOD_FIT
    if oppose >= support + 2:
        return Verdict.POOR_FIT
    return Verdict.UNCERTAIN


def _ranked(items: list[EvidenceItem]) -> list[EvidenceItem]:
    stance_rank = {Stance.SUPPORT: 0, Stance.OPPOSE: 1, Stance.MIXED: 2}
    return sorted(
        items,
        key=lambda item: (
            -(item.helpful_votes or 0),
            -(1 if item.verified_purchase else 0),
            stance_rank[item.stance],
            item.id,
        ),
    )


def _aspect_result(aspect: Aspect, items: list[EvidenceItem]) -> AspectResult:
    support = sum(item.stance is Stance.SUPPORT for item in items)
    oppose = sum(item.stance is Stance.OPPOSE for item in items)
    mixed = sum(item.stance is Stance.MIXED for item in items)
    total = len(items)
    verdict = aspect_verdict(support, oppose, total)
    label = ASPECT_LABELS[aspect]
    if verdict is Verdict.UNAVAILABLE:
        summary = f"{label}的直接证据少于3条，暂不判断适配方向。"
    elif verdict is Verdict.GOOD_FIT:
        summary = f"{label}的支持证据占优，但仍需结合原评论与样本范围判断。"
    elif verdict is Verdict.POOR_FIT:
        summary = f"{label}的反对证据占优，可能与当前需求存在冲突。"
    else:
        summary = f"{label}的正反证据接近或存在混合观点，结论不确定。"
    return AspectResult(
        aspect=aspect,
        verdict=verdict,
        evidence_strength=evidence_strength(total),
        support_count=support,
        oppose_count=oppose,
        mixed_count=mixed,
        summary=summary,
        evidence_ids=[item.id for item in _ranked(items)[:12]],
    )


def _overall_verdict(aspects: list[AspectResult], priorities: dict[Aspect, int]) -> Verdict:
    available = [item for item in aspects if item.verdict is not Verdict.UNAVAILABLE]
    if not available:
        return Verdict.UNAVAILABLE
    score = 0
    for result in available:
        direction = {
            Verdict.GOOD_FIT: 1,
            Verdict.POOR_FIT: -1,
            Verdict.UNCERTAIN: 0,
            Verdict.UNAVAILABLE: 0,
        }[result.verdict]
        score += direction * priorities[result.aspect]
    if score >= 2:
        return Verdict.GOOD_FIT
    if score <= -2:
        return Verdict.POOR_FIT
    return Verdict.UNCERTAIN


def _report_id(product_id: str, need: ParsedNeed) -> str:
    canonical = json.dumps(need.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{product_id}\n{canonical}".encode("utf-8")).hexdigest()[:16]
    return f"report-{digest}"


def _comparison_id(request: CompareRequest) -> str:
    canonical = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return "compare-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _warning(value: str) -> str:
    return value.strip()[:180]


class TingjianService:
    def __init__(self, settings: Settings, store: EvidenceStore) -> None:
        self.settings = settings
        self.store = store
        self._qwen = QwenClient(settings) if settings.qwen_enabled else None

    def parse_need(self, request: NeedParseRequest) -> NeedParseResponse:
        warnings = list(self.store.warnings)
        if self._qwen is not None:
            try:
                need = self._qwen.parse_need(request)
                return NeedParseResponse(
                    need=need,
                    mode=RuntimeMode.QWEN,
                    warnings=[_warning(item) for item in warnings[:8]],
                )
            except ModelClientError:
                warnings.append("模型需求解析失败，已自动使用本地规则。")
        need = parse_need_locally(request)
        return NeedParseResponse(
            need=need,
            mode=RuntimeMode.LOCAL_RULES,
            warnings=[_warning(item) for item in warnings[:8]],
        )

    def build_report(self, request: ReportRequest) -> ReportResponse:
        product = self.store.get_product(request.product_id)
        if product is None:
            raise KeyError(request.product_id)

        priorities = {item.name: item.priority for item in request.need.aspects}
        aspect_items = {
            preference.name: self.store.evidence_for(
                request.product_id, aspect=preference.name
            )
            for preference in request.need.aspects
        }
        aspect_results = [
            _aspect_result(preference.name, aspect_items[preference.name])
            for preference in request.need.aspects
        ]
        verdict = _overall_verdict(aspect_results, priorities)
        all_relevant = [item for items in aspect_items.values() for item in items]
        overall_strength = evidence_strength(len(all_relevant))

        advantages = [
            f"{ASPECT_LABELS[item.aspect]}：支持证据相对占优。"
            for item in aspect_results
            if item.verdict is Verdict.GOOD_FIT
        ][:6]
        risks = [
            f"{ASPECT_LABELS[item.aspect]}：反对证据相对占优。"
            for item in aspect_results
            if item.verdict is Verdict.POOR_FIT
        ][:6]
        unknowns = [
            f"{ASPECT_LABELS[item.aspect]}："
            + ("直接证据不足。" if item.verdict is Verdict.UNAVAILABLE else "观点存在冲突。")
            for item in aspect_results
            if item.verdict in {Verdict.UNAVAILABLE, Verdict.UNCERTAIN}
        ][:6]
        verdict_text = {
            Verdict.GOOD_FIT: "较匹配",
            Verdict.POOR_FIT: "较不匹配",
            Verdict.UNCERTAIN: "不确定",
            Verdict.UNAVAILABLE: "证据不足",
        }[verdict]
        summary = (
            f"基于{len(all_relevant)}条与当前关注维度直接相关的证据，"
            f"{product.display_name}的适配方向为“{verdict_text}”。"
            "该方向与证据强度是两个独立指标。"
        )

        preview: list[EvidenceItem] = []
        for preference in request.need.aspects:
            preview.extend(_ranked(aspect_items[preference.name])[:2])
        preview = list(dict.fromkeys(item.id for item in preview)) and [
            next(item for item in all_relevant if item.id == evidence_id)
            for evidence_id in dict.fromkeys(item.id for item in preview)
        ]
        preview = preview[:12]
        citation_ids = [item.id for item in preview]
        warnings = list(self.store.warnings)
        actual_mode = RuntimeMode.LOCAL_RULES
        model_name: str | None = None

        if self._qwen is not None and preview:
            try:
                generated = self._qwen.generate_report_copy(
                    user_need=request.need.model_dump(mode="json"),
                    product=product.model_dump(mode="json"),
                    aspect_results=[item.model_dump(mode="json") for item in aspect_results],
                    evidence=[item.model_dump(mode="json") for item in preview],
                    allowed_citation_ids=set(citation_ids),
                )
                summary = generated["summary"]
                advantages = generated["advantages"]
                risks = generated["risks"]
                unknowns = generated["unknowns"]
                citation_ids = generated["citation_ids"]
                actual_mode = RuntimeMode.QWEN
                model_name = self.settings.qwen_report_model
            except ModelClientError:
                warnings.append("模型报告生成失败，已自动使用可追溯的规则模板。")

        disclaimer = "匹配方向和证据强度由启发式规则计算；生成文本不得替代查看原证据。"
        if self.store.uses_demo_cache:
            disclaimer += " 当前内容为演示缓存，不代表真实商品表现。"
        return ReportResponse(
            report_id=_report_id(request.product_id, request.need),
            product=product,
            need=request.need,
            verdict=verdict,
            evidence_strength=overall_strength,
            summary=summary,
            advantages=advantages,
            risks=risks,
            unknowns=unknowns,
            aspects=aspect_results,
            citation_ids=citation_ids,
            evidence_preview=preview,
            warnings=[_warning(item) for item in warnings[:8]],
            meta=RuntimeMeta(
                mode=actual_mode,
                model=model_name,
                generated_at=datetime.now(UTC),
                is_demo_cache=self.store.uses_demo_cache,
                disclaimer=disclaimer,
            ),
        )

    def compare(self, request: CompareRequest) -> CompareResponse:
        reports = [
            self.build_report(ReportRequest(product_id=product_id, need=request.need))
            for product_id in request.product_ids
        ]
        scores = {report.product.id: self._score_report(report, request.need) for report in reports}
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        winner = ordered[0][0] if ordered[0][1] > ordered[1][1] else None
        if winner is None:
            conclusion = "两款样本在当前需求下的规则得分接近，建议逐维查看证据后再决定。"
        else:
            winner_name = next(report.product.display_name for report in reports if report.product.id == winner)
            conclusion = f"按当前关注维度和优先级，{winner_name}的证据方向相对更有利。"

        aspect_rows: list[AspectComparisonRow] = []
        for preference in request.need.aspects:
            products = {
                report.product.id: next(
                    item for item in report.aspects if item.aspect is preference.name
                )
                for report in reports
            }
            aspect_rows.append(AspectComparisonRow(aspect=preference.name, products=products))

        modes = {report.meta.mode for report in reports}
        warnings = list(dict.fromkeys(item for report in reports for item in report.warnings))
        return CompareResponse(
            comparison_id=_comparison_id(request),
            need=request.need,
            winner_product_id=winner,
            conclusion=conclusion,
            products=[
                ProductComparisonSummary(
                    product=report.product,
                    verdict=report.verdict,
                    evidence_strength=report.evidence_strength,
                    summary=report.summary,
                    report_id=report.report_id,
                )
                for report in reports
            ],
            aspect_rows=aspect_rows,
            warnings=[_warning(item) for item in warnings[:8]],
            meta=RuntimeMeta(
                mode=RuntimeMode.QWEN if modes == {RuntimeMode.QWEN} else RuntimeMode.LOCAL_RULES,
                model=self.settings.qwen_report_model if modes == {RuntimeMode.QWEN} else None,
                generated_at=datetime.now(UTC),
                is_demo_cache=self.store.uses_demo_cache,
                disclaimer="比较只反映同一需求下当前证据集的相对方向，不是商品综合排名。",
            ),
        )

    @staticmethod
    def _score_report(report: ReportResponse, need: ParsedNeed) -> int:
        priorities = {item.name: item.priority for item in need.aspects}
        direction = {
            Verdict.GOOD_FIT: 1,
            Verdict.POOR_FIT: -1,
            Verdict.UNCERTAIN: 0,
            Verdict.UNAVAILABLE: 0,
        }
        return sum(direction[item.verdict] * priorities[item.aspect] for item in report.aspects)
