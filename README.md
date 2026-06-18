# S.upervisor

> 자연어 상담 대화를 입력받아 **3분 내 세후(after-tax) 포트폴리오 제안서**를 생성하는 VVIP 전용 PB 대시보드.
>
> 삼성증권 영크리에이터 15기 4조 · PB Insight 과제

PB가 VVIP 고객과 나눈 상담을 그대로 녹취해 넣으면, 투자성향(IPS)을 구조화하고
세후 관점의 포트폴리오 비교·스트레스 테스트·근거 있는 인사이트까지 한 화면에서 끝낸다.

## 핵심 메시지 — "AI를 신뢰 가능하게 길들였다"

생성형 AI를 상담에 쓰되, **답이 매번 달라지거나 출처를 모르는** 문제를 설계로 통제했다.
우리가 잡은 5개의 축:

| 축 | 의미 | 구현 근거 |
| --- | --- | --- |
| **재현성** | 같은 입력 → 항상 같은 출력 | 계산·요약에 `now/random/uuid` 금지, LLM `temperature=0`, 재현성 회귀 테스트(`backend/tests/test_reproducibility.py`) |
| **감사추적성** | 답변의 근거를 항상 제시 | `/rag/insight` 응답에 출처 청크(citation)와 `as_of` 시각 동봉 |
| **세후계산** | 세전이 아닌 세후로 판단 | 세금 규칙은 LLM이 아니라 하드코딩 **규칙표**(`supabase` `tax_rule`)로 관리, LLM은 계산하지 않고 결과 숫자만 설명 |
| **세법 최신성** | 세율·세법을 코드에 박지 않음 | 근거·변경 이력이 추적되는 규칙표(`tax_rule` + audit 컬럼)로 분리 관리 |
| **데이터 거버넌스** | 비밀·개인정보 통제 | 비밀키는 서버측 `.env`(service_role 등), 클라이언트엔 anon/public 키만, Supabase RLS 골격 |

## 기술 스택

| 영역 | 사용 기술 | 배포 |
| --- | --- | --- |
| 프론트엔드 | Next.js · TypeScript · TailwindCSS · shadcn/ui · recharts · Zustand | **Vercel** |
| 백엔드 | FastAPI (Python) | **Render** |
| DB | Supabase — PostgreSQL + pgvector | — |
| AI | Azure OpenAI (`gpt-4o` LLM, `text-embedding-3-small` 임베딩) · Azure Speech (STT) | — |

> 프론트는 **pnpm**으로 통일한다(npm/yarn 혼용 금지).

## 아키텍처 개요

원페이지 3분할 대시보드:

```
┌──────────────┬──────────────────────┬──────────────────┐
│  좌: 지능형 입력  │   중앙: 정량 엔진       │  우: 인사이트       │
│                │                      │                  │
│  상담 녹취 STT    │   세후 계산           │  스트레스 테스트     │
│  화자 매핑        │   포트폴리오 비교(A/B) │  RAG 인사이트       │
│  IPS(RRTTLLU) 조율│                      │  (출처 citation)   │
└──────────────┴──────────────────────┴──────────────────┘
```

### 백엔드 엔드포인트 (develop 기준 실제 구현)

| 메서드 · 경로 | 설명 |
| --- | --- |
| `GET /health` | 헬스 체크 |
| `POST /consultations/stt` | 상담 오디오 업로드 → STT·화자 매핑 → IPS(RRTTLLU) 추출 → 스냅샷 저장 |
| `GET /consultations` | 상담 목록 조회 |
| `GET /consultations/detail` | 상담 상세 조회 |
| `GET /consultations/initial-ips` | 고객 초기(디폴트) IPS 조회 |
| `POST /rag/insight` | 질의 임베딩 → pgvector 검색 → 답변 + 출처(citation) 반환 |
| `POST /tax/insight` | 절세 계산 결과(JSON)를 `gpt-4o`로 요약(temperature=0), 실패 시 템플릿 폴백 |

## 핵심 설계 원칙

신뢰 가능한 AI를 만들기 위한, 코드로 강제되는 규칙들:

- **세금 규칙은 하드코딩 규칙표.** 세율·한도·조건은 LLM이 추정하지 않고 `tax_rule`
  규칙표에 둔다. LLM(`/tax/insight`)은 **계산하지 않고** 주어진 결과 숫자만 한국어로 요약한다.
- **실시간 데이터는 RAG에 임베딩하지 않는다.** 시세 등 변동 데이터는 임베딩 대상이 아니라
  호출 시점에 직접 조회하는 것을 원칙으로 한다.
- **계산·요약 함수의 결정성.** `random`·`datetime.now()`·`uuid` 같은 비결정 호출을 쓰지 않고,
  시각이 필요하면 외부에서 주입한다. 재현성은 골든/불변식 회귀 테스트로 지킨다.
- **비밀키는 서버측에만.** `.env`(추적 제외)로만 읽고 하드코딩하지 않는다. `.env.example`만 커밋한다.

> 자세한 금융 도메인·보안 규칙은 [`AGENTS.md`](AGENTS.md), [`SECURITY.md`](SECURITY.md) 참조.

## 레포 구조

```
VVIP_PB_Advisor/
├── frontend/          # Next.js 대시보드 UI
├── backend/
│   └── app/
│       ├── routers/   # API 엔드포인트 (consultations · rag · tax)
│       ├── services/  # STT 파이프라인 · IPS 추출 · 세금 요약 · DART
│       ├── stt/       # STT · 화자 매핑 · RRTTLLU 추출
│       ├── rag/       # RAG 검색·생성 (Azure 임베딩 + pgvector)
│       ├── schemas/   # Pydantic 모델
│       ├── core/      # 설정(config) · Azure 클라이언트
│       └── db/        # Supabase 클라이언트
├── supabase/          # DB 마이그레이션 · 시드 (PostgreSQL + pgvector)
├── .github/           # PR·이슈 템플릿, CI 워크플로
├── AGENTS.md          # AI 코드 어시스턴트 작업 규칙
├── CONTRIBUTING.md    # 협업 규칙 (브랜치 전략·커밋·PR)
└── README.md
```

## 로컬 실행

> ⚠️ **백엔드를 먼저 띄워야** 프론트가 실데이터를 받는다. 데모 전에 백엔드를 미리 워밍업할 것.

### 1) 백엔드 (`backend/`)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
```

`backend/.env` 에 필요한 변수명 (값은 `.env.example` 참고, 비밀은 커밋 금지):

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
AZURE_OPENAI_LLM_DEPLOYMENT
AZURE_OPENAI_EMBEDDING_DEPLOYMENT
AZURE_SPEECH_KEY
AZURE_SPEECH_REGION
DART_API_KEY
ALLOWED_ORIGINS
```

### 2) 프론트엔드 (`frontend/`)

```bash
cd frontend
pnpm install
pnpm dev
# http://localhost:3000
```

`frontend/.env.local` 에 필요한 변수명:

```
NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

## 협업 (GitFlow)

- `feature/*` → `develop` → `main` 순으로 흐른다. **`main` 직접 푸시 금지.**
- 모든 변경은 PR로, **최소 1명 리뷰 승인 + CI 통과**(ruff lint · 빌드) 후 머지한다.
- 커밋 메시지는 `타입: 설명`(한국어), 타입은 `feat`·`fix`·`docs`·`chore`·`refactor`·`test`.

자세한 규칙은 [`CONTRIBUTING.md`](CONTRIBUTING.md) 참조.

## 팀 구성

| 역할 | 리드 | 페어 |
| --- | --- | --- |
| 프론트엔드 | 다경 | 준호 (UX), 중현 (스캐폴드) |
| 백엔드 | 중현 | — |
| AI + 기획 | 준호 (PM), 중현 (팀장) | 지은 (AI 기획), 승민 (AI 개발) |
| 도메인 스터디 | 다경 | 준호·지은 (차별화 A+D), 승민·중현 (차별화 B+C) |
| 발표 자료 | 전원 | 준호·다경 (디자인), 중현 (피드백) |

- 발표자·영상팀은 추후 논의
- 발표 때 강조할 내용은 개발 단계 중 미리 정리해 둘 것
