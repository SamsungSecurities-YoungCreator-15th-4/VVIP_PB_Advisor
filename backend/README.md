# Backend — VVIP Asset Advisor Hub

FastAPI 기반 백엔드. 현재는 `/health` 엔드포인트만 있는 뼈대 상태이며, 실제 엔드포인트는 기획 확정 후 추가한다.

## 요구 사항

- Python 3.11 이상 권장

## 로컬 실행

```bash
# 1) 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# 2) 의존성 설치
pip install -r requirements.txt

# 3) 개발 서버 실행 (http://127.0.0.1:8000)
uvicorn app.main:app --reload
```

## 헬스 체크

```bash
curl http://127.0.0.1:8000/health
# => {"status":"ok"}
```

## 환경 변수

`.env.example`을 복사해 `.env`로 사용한다. `.env`는 절대 커밋하지 않는다.

```bash
cp .env.example .env
```
