# 이 파일은 뼈대다. 실제 엔드포인트는 기획 확정 후 추가한다.
from fastapi import FastAPI

app = FastAPI(title="VVIP Asset Advisor Hub API")

# TODO(다음 PR): 프론트(Vercel)에서 호출 시작하면 CORSMiddleware 추가 필요.
#   from fastapi.middleware.cors import CORSMiddleware
#   허용 origin은 환경변수로 받아 하드코딩 금지. 이번 PR(헬스체크 전용)에서는 불필요.


@app.get("/health")
def health() -> dict[str, str]:
    # 배포 헬스체크용: 의존성·DB 호출 없이 즉답한다.
    return {"status": "ok", "service": "vvip-pb-advisor"}
