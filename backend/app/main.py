from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.market.routes import router as market_router
from app.routers import clients, dart, rag, tax
from app.routers.consultations import router as consultations_router
from app.routers.portfolio import router as portfolio_router

app = FastAPI(title="VVIP Asset Advisor Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(consultations_router)
app.include_router(clients.router)
app.include_router(rag.router)
app.include_router(tax.router)
app.include_router(portfolio_router)
app.include_router(dart.router)
app.include_router(market_router)

# 중요:
# app.portfolio_logic.portfolio_logic.router는 등록하지 않는다.
# 계산 함수와 모델은 서비스 계층에서 import해 재사용하지만,
# PR #74에 남아 있던 중복 GET/POST 엔드포인트는 외부 API로 노출하지 않는다.


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vvip-pb-advisor"}
