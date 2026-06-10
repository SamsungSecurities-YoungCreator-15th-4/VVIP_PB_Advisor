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

## 데이터베이스 (DB)

DB 스키마·마이그레이션은 **Supabase CLI**로 관리하며 레포 루트 **`supabase/`** 에 있다. (과거 `backend/db/`는 폐지)

| 항목 | 위치 |
| --- | --- |
| baseline (v0.1, 9개 테이블·RAG 함수·RLS) | `supabase/migrations/20260605000000_baseline_v0_1.sql` |
| 0001 (FK 인덱스 3건 + RAG 임계값) | `supabase/migrations/20260605000001_add_fk_indexes_and_threshold.sql` |
| CLI 설정 | `supabase/config.toml` |

새 마이그레이션은 `supabase migration new <이름>` 으로 만든다. 운영 절차(로그인·링크·동기화)는 **[`../supabase/README.md`](../supabase/README.md)** 참고.
