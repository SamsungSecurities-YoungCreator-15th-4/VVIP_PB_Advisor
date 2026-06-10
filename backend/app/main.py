import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.market.routes import router as market_router

app = FastAPI(title="VVIP Asset Advisor Hub API")

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
    return {"status": "ok"}
