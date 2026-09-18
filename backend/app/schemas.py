from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


ShortText = Annotated[StrictStr, Field(min_length=1, max_length=180)]
EvidenceId = Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
ProductId = Annotated[StrictStr, Field(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]


class StrictModel(BaseModel):
    """Base contract for every public request and response."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class Scene(str, Enum):
    COMMUTE = "commute"
    MEETING = "meeting"
    EXERCISE = "exercise"
    LONG_WEAR = "long_wear"
    GENERAL = "general"


class Aspect(str, Enum):
    NOISE_CANCELLATION = "noise_cancellation"
    CALL_QUALITY = "call_quality"
    CONNECTION = "connection"
    COMFORT = "comfort"
    BATTERY = "battery"
    SOUND_QUALITY = "sound_quality"


class Stance(str, Enum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    MIXED = "mixed"


class Verdict(str, Enum):
    GOOD_FIT = "good_fit"
    UNCERTAIN = "uncertain"
    POOR_FIT = "poor_fit"
    UNAVAILABLE = "unavailable"


class EvidenceStrength(str, Enum):
    INSUFFICIENT = "insufficient"
    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


class RuntimeMode(str, Enum):
    LOCAL_RULES = "local_rules"
    QWEN = "qwen"


class EvidenceSourceKind(str, Enum):
    DEMO_CACHE = "demo_cache"
    DERIVED_DATASET = "derived_dataset"


class AspectPreference(StrictModel):
    name: Aspect
    priority: Annotated[StrictInt, Field(ge=1, le=3)] = 2


class Constraint(StrictModel):
    code: Annotated[StrictStr, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]
    label: ShortText
    hard: StrictBool = True


class ParsedNeed(StrictModel):
    raw_text: Annotated[StrictStr, Field(max_length=300)] = ""
    scenes: Annotated[list[Scene], Field(min_length=1, max_length=5)]
    aspects: Annotated[list[AspectPreference], Field(min_length=1, max_length=6)]
    constraints: Annotated[list[Constraint], Field(max_length=8)] = Field(default_factory=list)

    @field_validator("scenes")
    @classmethod
    def scenes_must_be_unique(cls, value: list[Scene]) -> list[Scene]:
        if len(value) != len(set(value)):
            raise ValueError("scenes must not contain duplicates")
        return value

    @field_validator("aspects")
    @classmethod
    def aspects_must_be_unique(cls, value: list[AspectPreference]) -> list[AspectPreference]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("aspects must not contain duplicates")
        return value


class NeedParseRequest(StrictModel):
    text: Annotated[StrictStr, Field(max_length=300)] = ""
    selected_scenes: Annotated[list[Scene], Field(max_length=5)] = Field(default_factory=list)
    selected_aspects: Annotated[list[Aspect], Field(max_length=6)] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_some_input(self) -> "NeedParseRequest":
        if not self.text and not self.selected_scenes and not self.selected_aspects:
            raise ValueError("provide text, selected_scenes, or selected_aspects")
        if len(self.selected_scenes) != len(set(self.selected_scenes)):
            raise ValueError("selected_scenes must not contain duplicates")
        if len(self.selected_aspects) != len(set(self.selected_aspects)):
            raise ValueError("selected_aspects must not contain duplicates")
        return self


class NeedParseResponse(StrictModel):
    need: ParsedNeed
    mode: RuntimeMode
    warnings: Annotated[list[ShortText], Field(max_length=8)] = Field(default_factory=list)


class ProductSummary(StrictModel):
    id: ProductId
    display_name: ShortText
    description: Annotated[StrictStr, Field(min_length=1, max_length=300)]
    source_kind: EvidenceSourceKind


class EvidenceItem(StrictModel):
    id: EvidenceId
    product_id: ProductId
    aspect: Aspect
    stance: Stance
    quote: Annotated[StrictStr, Field(min_length=1, max_length=600)]
    summary_zh: Annotated[StrictStr, Field(min_length=1, max_length=240)]
    rating: Annotated[StrictInt, Field(ge=1, le=5)] | None = None
    helpful_votes: Annotated[StrictInt, Field(ge=0)] | None = None
    verified_purchase: StrictBool | None = None
    source_kind: EvidenceSourceKind
    source_ref: Annotated[StrictStr, Field(min_length=1, max_length=120)]


class EvidenceListResponse(StrictModel):
    product_id: ProductId
    total: Annotated[StrictInt, Field(ge=0)]
    items: list[EvidenceItem]
    warnings: Annotated[list[ShortText], Field(max_length=8)] = Field(default_factory=list)


class AspectResult(StrictModel):
    aspect: Aspect
    verdict: Verdict
    evidence_strength: EvidenceStrength
    support_count: Annotated[StrictInt, Field(ge=0)]
    oppose_count: Annotated[StrictInt, Field(ge=0)]
    mixed_count: Annotated[StrictInt, Field(ge=0)]
    summary: Annotated[StrictStr, Field(min_length=1, max_length=280)]
    evidence_ids: Annotated[list[EvidenceId], Field(max_length=12)]


class ReportRequest(StrictModel):
    product_id: ProductId
    need: ParsedNeed


class RuntimeMeta(StrictModel):
    mode: RuntimeMode
    model: StrictStr | None = None
    generated_at: datetime
    is_demo_cache: StrictBool
    disclaimer: Annotated[StrictStr, Field(min_length=1, max_length=300)]


class ReportResponse(StrictModel):
    report_id: Annotated[StrictStr, Field(pattern=r"^report-[a-f0-9]{16}$")]
    product: ProductSummary
    need: ParsedNeed
    verdict: Verdict
    evidence_strength: EvidenceStrength
    summary: Annotated[StrictStr, Field(min_length=1, max_length=400)]
    advantages: Annotated[list[ShortText], Field(max_length=6)]
    risks: Annotated[list[ShortText], Field(max_length=6)]
    unknowns: Annotated[list[ShortText], Field(max_length=6)]
    aspects: Annotated[list[AspectResult], Field(min_length=1, max_length=6)]
    citation_ids: Annotated[list[EvidenceId], Field(max_length=24)]
    evidence_preview: Annotated[list[EvidenceItem], Field(max_length=12)]
    warnings: Annotated[list[ShortText], Field(max_length=8)] = Field(default_factory=list)
    meta: RuntimeMeta


class CompareRequest(StrictModel):
    product_ids: Annotated[list[ProductId], Field(min_length=2, max_length=2)]
    need: ParsedNeed

    @field_validator("product_ids")
    @classmethod
    def products_must_be_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != 2:
            raise ValueError("product_ids must contain two distinct products")
        return value


class ProductComparisonSummary(StrictModel):
    product: ProductSummary
    verdict: Verdict
    evidence_strength: EvidenceStrength
    summary: Annotated[StrictStr, Field(min_length=1, max_length=400)]
    report_id: Annotated[StrictStr, Field(pattern=r"^report-[a-f0-9]{16}$")]


class AspectComparisonRow(StrictModel):
    aspect: Aspect
    products: dict[ProductId, AspectResult]

    @field_validator("products")
    @classmethod
    def row_has_two_products(cls, value: dict[str, AspectResult]) -> dict[str, AspectResult]:
        if len(value) != 2:
            raise ValueError("an aspect comparison row must contain two products")
        return value


class CompareResponse(StrictModel):
    comparison_id: Annotated[StrictStr, Field(pattern=r"^compare-[a-f0-9]{16}$")]
    need: ParsedNeed
    winner_product_id: ProductId | None
    conclusion: Annotated[StrictStr, Field(min_length=1, max_length=400)]
    products: Annotated[list[ProductComparisonSummary], Field(min_length=2, max_length=2)]
    aspect_rows: Annotated[list[AspectComparisonRow], Field(min_length=1, max_length=6)]
    warnings: Annotated[list[ShortText], Field(max_length=8)] = Field(default_factory=list)
    meta: RuntimeMeta


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: Literal["tingjian-api"]
    version: Annotated[StrictStr, Field(pattern=r"^\d+\.\d+\.\d+$")]
    mode: RuntimeMode
    model_configured: StrictBool
    is_demo_cache: StrictBool
    evidence_source: EvidenceSourceKind
    products_loaded: Annotated[StrictInt, Field(ge=0)]
    evidence_loaded: Annotated[StrictInt, Field(ge=0)]


class ProductListResponse(StrictModel):
    items: list[ProductSummary]
