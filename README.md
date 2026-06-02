# VVIP Asset Advisor Hub

> 삼성증권 영크리에이터 15기 4조 · PB Insight 과제 — PB가 VVIP 고객 상담 시 사용하는 AI 기반 자산관리 대시보드.

## 프로젝트 목표

자연스러운 상담 대화를 입력받아, 단 **3분 만에** VVIP 맞춤형 세후 포트폴리오 제안서 출력까지 끝내는 PB 전용 도구를 만든다.

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 프론트엔드 | Next.js, TypeScript, TailwindCSS |
| 백엔드 | FastAPI (Python), yfinance |
| DB·인증 | Supabase (PostgreSQL) |
| 배포 | Vercel |
| 협업 | GitHub, Notion, Slack |

## 레포 구조

```
VVIP_PB_Advisor/
├── frontend/      # Next.js 프론트엔드 (PB 상담 대시보드 UI)
├── backend/       # FastAPI 백엔드 (시장 데이터·정량 지표·포트폴리오 연산)
├── docs/          # 기획·설계·협업 규칙 문서
├── .github/       # PR 템플릿 등 GitHub 관련 설정
├── AGENTS.md      # AI 에이전트(코드 어시스턴트)를 위한 작업 규칙
├── CLAUDE.md      # Claude Code 진입점 (AGENTS.md 참조)
├── .gitignore
└── README.md
```

## 시작하기 (Getting Started)

```bash
# 프론트엔드
cd frontend && pnpm install && pnpm dev

# 백엔드
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
```

> 프론트는 **pnpm**으로 통일합니다. npm/yarn 섞지 마세요.

## 로컬 실행

### 프론트엔드 (`frontend/`)

```bash
cd frontend
pnpm install
pnpm dev
# http://localhost:3000
```

### 백엔드 (`backend/`)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows는 .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# http://127.0.0.1:8000/health
```

## 팀 구성

| 역할 | 리드 | 페어 |
| --- | --- | --- |
| 프론트엔드 | 다경 | 준호 (UX) |
| 백엔드 | 중현 | — |
| AI + 기획 | 준호 (PM), 중현 (팀장) | 지은 (AI 기획), 승민 (AI 개발) |
| 도메인 스터디 | 다경 | 준호·지은 (차별화 A+D), 승민·중현 (차별화 B+C) |
| 발표 자료 | 전원 | 준호·다경 (디자인), 중현 (피드백) |

- 발표자·영상팀은 추후 논의
- 발표 때 강조할 내용은 개발 단계 중 미리 정리해 둘 것

## 개발 컨벤션

브랜치 전략과 PR 규칙은 [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)를 참조한다.
