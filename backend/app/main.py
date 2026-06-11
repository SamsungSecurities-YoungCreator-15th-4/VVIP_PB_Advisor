import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market.routes import router as market_router

app = FastAPI(title="VVIP Asset Advisor Hub API")

# 허용 origin은 환경변수로 받는다 (하드코딩 금지 — develop TODO 구현 완료).
_frontend_origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(market_router)


@app.get("/health")
def health() -> dict[str, str]:
    # 배포 헬스체크용: 의존성·DB 호출 없이 즉답한다.
    return {"status": "ok", "service": "vvip-pb-advisor"}
