from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, load_settings
from .demo_store import EvidenceStore
from .schemas import (
    Aspect,
    CompareRequest,
    CompareResponse,
    EvidenceListResponse,
    HealthResponse,
    NeedParseRequest,
    NeedParseResponse,
    ProductListResponse,
    ReportRequest,
    ReportResponse,
    Stance,
)
from .services import TingjianService


def create_app(
    *, settings: Settings | None = None, store: EvidenceStore | None = None
) -> FastAPI:
    settings = settings or load_settings()
    store = store or EvidenceStore.load_default()
    service = TingjianService(settings, store)
    application = FastAPI(
        title="听荐 API",
        version="0.1.0",
        description="基于可追溯评论证据的真无线耳机需求匹配演示 API。",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="tingjian-api",
            version="0.1.0",
            mode=settings.runtime_mode,
            model_configured=settings.qwen_enabled,
            is_demo_cache=store.uses_demo_cache,
            evidence_source=store.products[0].source_kind,
            products_loaded=len(store.products),
            evidence_loaded=store.evidence_count,
        )

    @application.get("/api/products", response_model=ProductListResponse)
    def products() -> ProductListResponse:
        return ProductListResponse(items=list(store.products))

    @application.post("/api/needs/parse", response_model=NeedParseResponse)
    def parse_need(payload: NeedParseRequest) -> NeedParseResponse:
        return service.parse_need(payload)

    @application.post("/api/reports", response_model=ReportResponse)
    def create_report(payload: ReportRequest) -> ReportResponse:
        try:
            return service.build_report(payload)
        except KeyError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "product_not_found", "product_id": payload.product_id},
            ) from exc

    @application.get(
        "/api/products/{product_id}/evidence", response_model=EvidenceListResponse
    )
    def product_evidence(
        product_id: str,
        aspect: Aspect | None = None,
        stance: Stance | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> EvidenceListResponse:
        if store.get_product(product_id) is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "product_not_found", "product_id": product_id},
            )
        items = store.evidence_for(product_id, aspect=aspect, stance=stance)
        return EvidenceListResponse(
            product_id=product_id,
            total=len(items),
            items=items[offset : offset + limit],
            warnings=list(store.warnings)[:8],
        )

    @application.post("/api/compare", response_model=CompareResponse)
    def compare(payload: CompareRequest) -> CompareResponse:
        missing = [item for item in payload.product_ids if store.get_product(item) is None]
        if missing:
            raise HTTPException(
                status_code=404,
                detail={"code": "product_not_found", "product_ids": missing},
            )
        return service.compare(payload)

    return application


app = create_app()
