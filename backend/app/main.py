# 이 파일은 뼈대다. 실제 엔드포인트는 기획 확정 후 추가한다.
from fastapi import FastAPI

app = FastAPI(title="VVIP Asset Advisor Hub API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
