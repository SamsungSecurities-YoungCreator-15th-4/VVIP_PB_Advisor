from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.consultations import router as consultations_router

from app.routers import rag

app = FastAPI(title="VVIP Asset Advisor Hub API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(consultations_router)
app.include_router(rag.router)


@app.get("/health")
def health() -> dict[str, str]:
    # 배포 헬스체크용: 의존성·DB 호출 없이 즉답한다.
    return {"status": "ok", "service": "vvip-pb-advisor"}
