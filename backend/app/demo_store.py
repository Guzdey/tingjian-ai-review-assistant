from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schemas import (
    Aspect,
    EvidenceItem,
    EvidenceSourceKind,
    ProductSummary,
    Stance,
)


PRODUCTS = (
    ProductSummary(
        id="demo-tws-a",
        display_name="样本耳机 A",
        description="偏向通勤降噪与长时间佩戴的匿名真无线耳机样本。",
        source_kind=EvidenceSourceKind.DEMO_CACHE,
    ),
    ProductSummary(
        id="demo-tws-b",
        display_name="样本耳机 B",
        description="偏向会议通话与连接稳定的匿名真无线耳机样本。",
        source_kind=EvidenceSourceKind.DEMO_CACHE,
    ),
)


# These excerpts are deliberately authored demo fixtures, not Amazon quotations.
# They let a clone run without a model key or the separately generated dataset.
_DEMO_ROWS: dict[str, dict[Aspect, list[tuple[Stance, str, str, int]]]] = {
    "demo-tws-a": {
        Aspect.NOISE_CANCELLATION: [
            (Stance.SUPPORT, "The train rumble becomes much less distracting with ANC on.", "开启降噪后，列车低频噪声干扰明显减小。", 5),
            (Stance.SUPPORT, "Noise cancelling works well for my daily subway commute.", "日常地铁通勤中降噪表现得到肯定。", 4),
            (Stance.SUPPORT, "It blocks steady office and airplane noise better than I expected.", "对办公室和飞机上的持续噪声抑制较好。", 5),
        ],
        Aspect.CALL_QUALITY: [
            (Stance.OPPOSE, "People say my voice turns thin when I call from a busy street.", "繁忙街道通话时，对方认为人声偏单薄。", 2),
            (Stance.MIXED, "Calls are clear indoors, but wind makes the microphone struggle.", "室内通话清楚，但有风时麦克风表现下降。", 3),
            (Stance.OPPOSE, "The microphone picks up too much station noise during meetings.", "车站环境开会时会拾取较多背景噪声。", 2),
        ],
        Aspect.CONNECTION: [
            (Stance.SUPPORT, "Pairing is quick and it normally reconnects as soon as I open the case.", "配对迅速，开盒后通常能自动回连。", 4),
            (Stance.OPPOSE, "The left earbud dropped out twice on a crowded commute.", "拥挤通勤时左耳曾出现两次断连。", 2),
            (Stance.MIXED, "Stable with my phone, although switching to the laptop takes an extra try.", "连接手机稳定，但切换电脑偶尔需重试。", 3),
        ],
        Aspect.COMFORT: [
            (Stance.SUPPORT, "The small shells stay comfortable through a three-hour work session.", "较小的腔体连续佩戴三小时仍较舒适。", 5),
            (Stance.SUPPORT, "They feel light and do not press against the outer ear.", "机身轻，未明显挤压外耳。", 4),
            (Stance.SUPPORT, "Once I changed the tips, the fit was secure without soreness.", "更换耳塞后佩戴稳固且没有明显酸痛。", 4),
        ],
        Aspect.BATTERY: [
            (Stance.MIXED, "Battery covers my commute, but ANC means I recharge every few days.", "续航可覆盖通勤，但开启降噪后需更频繁充电。", 3),
            (Stance.SUPPORT, "The case gets me through several short trips before charging.", "充电盒可支持多次短途使用。", 4),
            (Stance.OPPOSE, "The earbuds warn about low battery earlier than I expected.", "耳机出现低电量提醒的时间早于预期。", 2),
        ],
        Aspect.SOUND_QUALITY: [
            (Stance.SUPPORT, "Vocals are detailed and podcasts remain easy to follow on the train.", "人声细节清楚，乘车时播客内容易听清。", 4),
            (Stance.MIXED, "The sound is clean, though bass lovers may want more impact.", "声音干净，但重低音力度可能不足。", 3),
            (Stance.SUPPORT, "Music sounds balanced rather than overly boosted.", "音乐听感均衡，没有明显过度增益。", 4),
        ],
    },
    "demo-tws-b": {
        Aspect.NOISE_CANCELLATION: [
            (Stance.MIXED, "ANC reduces the hum, but announcements still come through clearly.", "降噪能减弱持续嗡鸣，但广播声仍较明显。", 3),
            (Stance.SUPPORT, "It takes the edge off traffic noise during my commute.", "通勤时可减轻交通噪声的干扰。", 4),
            (Stance.OPPOSE, "The cancellation is not strong enough for the loudest subway sections.", "在最吵的地铁路段，降噪强度不够。", 2),
        ],
        Aspect.CALL_QUALITY: [
            (Stance.SUPPORT, "Coworkers hear me clearly in video meetings without a headset mic.", "视频会议中同事能清楚听见人声。", 5),
            (Stance.SUPPORT, "The microphones keep my voice understandable in a cafe.", "咖啡店环境中麦克风仍能保持人声可懂度。", 4),
            (Stance.SUPPORT, "I use them for calls every day and nobody has complained about clarity.", "每天用于通话，未收到清晰度方面的负面反馈。", 5),
        ],
        Aspect.CONNECTION: [
            (Stance.SUPPORT, "Multipoint switching between my phone and laptop is reliable.", "手机和电脑之间的多点切换较可靠。", 5),
            (Stance.SUPPORT, "They reconnect quickly and have not randomly disconnected.", "回连速度快，未出现随机断连。", 5),
            (Stance.SUPPORT, "The signal stays stable when my phone is in another room.", "手机放在相邻房间时连接仍稳定。", 4),
        ],
        Aspect.COMFORT: [
            (Stance.MIXED, "Secure for walking, but the larger body becomes noticeable after two hours.", "步行时佩戴稳固，但两小时后较大的机身存在感明显。", 3),
            (Stance.SUPPORT, "The included tips give me a good seal without slipping.", "附带耳塞能形成良好密封且不易滑落。", 4),
            (Stance.OPPOSE, "My smaller ears feel pressure during long meetings.", "耳朵较小的用户在长时间会议中感到压迫。", 2),
        ],
        Aspect.BATTERY: [
            (Stance.SUPPORT, "One charge comfortably lasts through a full workday of mixed use.", "单次充电可覆盖一整天的混合使用。", 5),
            (Stance.SUPPORT, "The case provides enough extra power for a weekend away.", "充电盒的额外电量足以支持周末外出。", 4),
            (Stance.SUPPORT, "Battery drain is consistent and the percentage display is useful.", "电量消耗稳定，电量显示有参考价值。", 4),
        ],
        Aspect.SOUND_QUALITY: [
            (Stance.SUPPORT, "Speech and vocals sound clear with good separation.", "语音和人声清楚，分离度较好。", 4),
            (Stance.MIXED, "Bass is energetic, though it can cover fine detail in some tracks.", "低频有力度，但部分曲目中会遮盖细节。", 3),
            (Stance.SUPPORT, "The lively tuning works well for pop music and workouts.", "活跃的调音适合流行音乐和运动场景。", 4),
        ],
    },
}


def _built_in_evidence() -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for product_id, aspects in _DEMO_ROWS.items():
        product_alias = product_id.removeprefix("demo-tws-")
        for aspect, rows in aspects.items():
            short_aspect = aspect.value.replace("_", "-")
            for index, (stance, quote, summary, rating) in enumerate(rows, start=1):
                items.append(
                    EvidenceItem(
                        id=f"ev-{product_alias}-{short_aspect}-{index:02d}",
                        product_id=product_id,
                        aspect=aspect,
                        stance=stance,
                        quote=quote,
                        summary_zh=summary,
                        rating=rating,
                        helpful_votes=index - 1,
                        verified_purchase=True,
                        source_kind=EvidenceSourceKind.DEMO_CACHE,
                        source_ref=f"authored-demo:{product_alias}:{short_aspect}:{index}",
                    )
                )
    return items


def _whole_int(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize_product(raw: dict[str, Any]) -> dict[str, Any]:
    product_id = raw.get("id", raw.get("product_id"))
    return {
        "id": str(product_id).replace("demo_tws_", "demo-tws-").replace("_", "-")
        if product_id
        else product_id,
        "display_name": raw.get("display_name", raw.get("name")),
        "description": raw.get("description", "匿名真无线耳机派生数据样本。"),
        "source_kind": raw.get("source_kind", EvidenceSourceKind.DERIVED_DATASET.value),
    }


def _normalize_evidence(raw: dict[str, Any]) -> dict[str, Any]:
    evidence_id = raw.get("id", raw.get("evidence_id"))
    product_id = raw.get("product_id")
    quote = raw.get("quote", raw.get("key_sentence", raw.get("text")))
    summary = raw.get("summary_zh", raw.get("summary"))
    if not summary:
        summary = "该条派生评论涉及此维度；尚未生成中文摘要。"
    source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    source_ref = raw.get("source_ref")
    if not source_ref:
        source_ref = f"derived:{source.get('input_line', evidence_id or 'unknown')}"
    normalized_product_id = (
        str(product_id).replace("demo_tws_", "demo-tws-").replace("_", "-")
        if product_id
        else product_id
    )
    return {
        "id": evidence_id,
        "product_id": normalized_product_id,
        "aspect": raw.get("aspect"),
        "stance": raw.get("stance", raw.get("sentiment")),
        "quote": str(quote)[:600] if quote is not None else quote,
        "summary_zh": str(summary)[:240],
        "rating": _whole_int(raw.get("rating")),
        "helpful_votes": _whole_int(raw.get("helpful_votes", raw.get("helpful_vote"))),
        "verified_purchase": raw.get("verified_purchase"),
        "source_kind": raw.get("source_kind", EvidenceSourceKind.DERIVED_DATASET.value),
        "source_ref": str(source_ref)[:120],
    }


class EvidenceStore:
    """Validated, in-memory evidence store with a deterministic safe fallback."""

    def __init__(
        self,
        products: Iterable[ProductSummary],
        evidence: Iterable[EvidenceItem],
        *,
        warnings: Iterable[str] = (),
    ) -> None:
        self._products = {product.id: product for product in products}
        self._evidence = tuple(evidence)
        self.warnings = tuple(warnings)
        if set(self._products) != {"demo-tws-a", "demo-tws-b"}:
            raise ValueError("evidence store must contain demo-tws-a and demo-tws-b")
        unknown = {item.product_id for item in self._evidence} - set(self._products)
        if unknown:
            raise ValueError(f"evidence references unknown products: {sorted(unknown)}")

    @classmethod
    def built_in(cls, warning: str | None = None) -> "EvidenceStore":
        warnings = [warning] if warning else []
        warnings.append("当前使用仓库内置演示缓存；内容不是外部平台原评论。")
        return cls(PRODUCTS, _built_in_evidence(), warnings=warnings)

    @classmethod
    def load_default(cls) -> "EvidenceStore":
        explicit = os.environ.get("TINGJIAN_DEMO_DATA_PATH", "").strip()
        repo_root = Path(__file__).resolve().parents[2]
        candidates = [Path(explicit)] if explicit else [repo_root / "data" / "demo_derived.json"]
        for path in candidates:
            if not path.is_file():
                continue
            try:
                return cls.from_json(path)
            except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                return cls.built_in(f"派生数据读取失败，已安全降级：{exc}")
        return cls.built_in()

    @classmethod
    def from_json(cls, path: Path) -> "EvidenceStore":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("demo data root must be an object")
        raw_products = payload.get("products")
        raw_evidence = payload.get("evidence", payload.get("items"))
        if not isinstance(raw_products, list) or not isinstance(raw_evidence, list):
            raise ValueError("demo data requires products[] and evidence[]")
        products = [ProductSummary.model_validate(_normalize_product(row)) for row in raw_products]
        evidence = [EvidenceItem.model_validate(_normalize_evidence(row)) for row in raw_evidence]
        if not evidence:
            raise ValueError("demo data evidence[] cannot be empty")
        return cls(products, evidence)

    @property
    def products(self) -> tuple[ProductSummary, ...]:
        return tuple(self._products[key] for key in sorted(self._products))

    @property
    def evidence_count(self) -> int:
        return len(self._evidence)

    @property
    def uses_demo_cache(self) -> bool:
        return any(item.source_kind is EvidenceSourceKind.DEMO_CACHE for item in self._evidence)

    def get_product(self, product_id: str) -> ProductSummary | None:
        return self._products.get(product_id)

    def evidence_for(
        self,
        product_id: str,
        *,
        aspect: Aspect | None = None,
        stance: Stance | None = None,
    ) -> list[EvidenceItem]:
        return [
            item
            for item in self._evidence
            if item.product_id == product_id
            and (aspect is None or item.aspect is aspect)
            and (stance is None or item.stance is stance)
        ]
