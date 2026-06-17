from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.portfolio_logic.portfolio_logic import router as portfolio_router
from app.routers import rag, tax
from app.routers.consultations import router as consultations_router


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
app.include_router(tax.router)
app.include_router(portfolio_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "vvip-pb-advisor"}