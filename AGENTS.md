# AGENTS.md — VVIP Asset Advisor Hub

이 레포에서 일하는 모든 AI 에이전트(코드 어시스턴트)는 이 문서의 규칙을 따른다.

## 프로젝트 한 줄 소개

삼성증권 영크리에이터 15기 4조 · PB Insight 과제 — PB가 VVIP 고객 상담 시 사용하는 AI 기반 자산관리 대시보드.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 프론트엔드 | Next.js (pnpm), TypeScript, TailwindCSS, shadcn/ui, recharts, Zustand |
| 백엔드 | FastAPI (Python), yfinance |
| DB·인증 | Supabase (PostgreSQL + pgvector) — 접근 방식 A: supabase-py(RPC 전용) / B: psycopg3(직접 SQL) |
| 배포 | 프론트엔드 Vercel · 백엔드 Render |
| 협업 | GitHub, Notion, Slack |

## 레포 구조

```
VVIP_PB_Advisor/
├── frontend/      # Next.js 프론트엔드 (PB 상담 대시보드 UI)
├── backend/       # FastAPI 백엔드
│   └── app/
│       ├── routers/   # API 엔드포인트 (consultations, rag 등)
│       ├── stt/       # STT·화자 매핑·RRTTLLU 추출 (구 AI/stt 에서 이동)
│       ├── rag/       # RAG 검색부 (Azure 임베딩 + pgvector)
│       ├── services/  # STT 파이프라인·IPS 추출 등 비즈니스 로직
│       ├── schemas/   # Pydantic 모델
│       ├── core/      # 설정(config)
│       └── db/        # Supabase 클라이언트
├── supabase/      # DB 마이그레이션·시드 (PostgreSQL + pgvector)
├── CONTRIBUTING.md # 협업 규칙(브랜치 전략·커밋·PR)
└── .github/       # PR 템플릿 등 GitHub 관련 설정
```

## 작업 규칙

- **디렉터리 경계**: 프론트엔드 작업은 `frontend/`, 백엔드 작업은 `backend/` 안에서만 한다. 두 영역을 동시에 건드리는 변경은 PR을 분리하는 것을 우선 고려한다.
- **커밋 메시지**: 한국어로, `타입: 설명` 형식. 타입은 `feat`, `fix`, `docs`, `chore`, `refactor`, `test` 중 하나.
  - 예) `feat: 포트폴리오 시뮬레이션 입력 폼 추가`
- **빌드/실행 확인**: 푸시 전 반드시 로컬에서 빌드와 실행이 되는지 확인한다. 프론트엔드는 `pnpm build`, 백엔드는 최소 `uvicorn app.main:app`이 떠야 한다.
- **덮어쓰기 알림**: 기존 파일을 지우거나 덮어쓰기 전 사용자에게 먼저 알리고 동의를 받는다.
- **비밀 정보 금지**: `.env` 파일과 모든 비밀키는 절대 커밋하지 않는다. `.env.example`만 추적 대상이다.

## 프론트엔드 작업 시 주의 (Next.js 16.x)

이 프로젝트가 사용하는 Next.js는 학습 데이터 시점 이후의 버전(16.x)이라 API·관례·파일 구조가 다를 수 있다. 코드를 쓰기 전 `frontend/node_modules/next/dist/docs/`에서 관련 가이드를 먼저 읽고, 사용 중단(deprecation) 경고는 그때그때 반영한다.

## 금융 도메인 주의사항

이 프로젝트는 PB가 실제 VVIP 상담에 사용하는 **금융 의사결정 보조 도구**다. 그래서 다음을 반드시 지킨다.

- **세금·법률 계산 로직은 함부로 추정하지 않는다.** 근거(법령·국세청 안내·논문·교과서 등 명확한 출처)가 있는 수식만 구현하고, 코드 주석으로 출처를 남긴다.
- **정량 지표(샤프지수·MDD·변동성 등)는 가짜/더미 데이터가 아니라 실제 수식과 실제 시장 데이터로 계산한다.** "일단 동작하게" 임의 값을 박아두지 않는다. 데이터가 없으면 함수 자체를 만들지 말고, 데이터 소스부터 연결한 뒤 작성한다.
- **숫자가 화면에 표시되면 그 숫자의 출처와 계산식이 코드에서 추적 가능해야 한다.**

## 보안

- API 키, 팀 계정 정보, 비밀번호를 코드·커밋·이슈·PR 본문 어디에도 포함하지 않는다.
- 외부 API 호출 시 키는 환경변수로만 읽는다. 하드코딩 금지.
- 사용자(고객) 정보를 다루는 코드는 로깅 시 PII 마스킹을 고려한다.
