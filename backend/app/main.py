from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.market.routes import router as market_router
from app.portfolio.portfolio_logic import router as portfolio_router
from app.routers import auth, clients, dart, portfolio_insight, rag, tax
from app.routers.consultations import router as consultations_router

app = FastAPI(title="VVIP Asset Advisor Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    # 고정 목록(localhost 등) 외에 Vercel 배포 도메인은 정규식으로 허용(프리뷰 URL 가변).
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(consultations_router)
app.include_router(clients.router)
app.include_router(rag.router)
app.include_router(tax.router)
app.include_router(portfolio_router)
app.include_router(portfolio_insight.router)
app.include_router(dart.router)
app.include_router(market_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vvip-pb-advisor"}
