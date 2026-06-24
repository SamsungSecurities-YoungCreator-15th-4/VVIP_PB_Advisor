"""Portfolio logic package — VVIP PB 포트폴리오 분석 엔진.

서브모듈 구조:
    constants      — 기본설정·기준표
    assets         — 자산군 정의
    models         — 요청/응답 Pydantic 모델
    utils          — 기본 유틸
    prices         — 가격 데이터 (yfinance)
    expected_returns — 기대수익률
    tax_accounts   — 세금/계좌
    metrics        — 지표 계산·기준표 평가
    generation     — 포트폴리오 생성/점수화
    responses      — 응답 빌드
    analysis       — 전체 분석 실행
    adapters       — API 입력 어댑터
    formatters     — API 응답 포맷터
    router         — FastAPI 엔드포인트

portfolio_logic.py는 하위 호환을 위한 re-export 파사드.
"""
