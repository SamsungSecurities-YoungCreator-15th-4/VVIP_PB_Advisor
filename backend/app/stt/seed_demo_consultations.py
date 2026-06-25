"""최종 발표 라이브 시연용 STT 상담 데이터 시드.

실행 위치:
    cd backend
    python app/stt/seed_demo_consultations.py

필요 환경변수:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from app.db.supabase import get_supabase  # noqa: E402
from app.services.ips import build_ips_snapshot_payload  # noqa: E402


class DemoConsultation(TypedDict):
    customer_name: str
    seed_key: str
    topic: str
    transcript_json: list[dict[str, str]]
    ips_json: dict[str, object]


def _line(speaker_role: str, text: str, utterance_time: str) -> dict[str, str]:
    return {
        "speaker_role": speaker_role,
        "text": text,
        "utterance_time": utterance_time,
    }


DEMO_CONSULTATIONS: list[DemoConsultation] = [
    {
        "customer_name": "김성삼",
        "seed_key": "kim-01-jeonse-gift",
        "topic": "자녀 전세자금과 장기 증여 계획",
        "transcript_json": [
            _line("PB", "김성삼 고객님, 오늘은 자녀 전세자금과 증여 계획을 같이 점검해 보겠습니다.", "00:01"),
            _line("고객", "내년 가을에 자녀가 독립할 수 있어서 전세자금 3억 원은 따로 빼두고 싶습니다. 전체 금융자산은 18억 원 정도입니다.", "00:09"),
            _line("PB", "그러면 3억 원은 단기 유동성 자금으로 두고, 나머지 15억 원은 장기 운용과 증여 일정을 함께 봐야겠습니다.", "00:22"),
            _line("고객", "맞습니다. 한 번에 증여하기보다는 세금 부담을 줄이면서 10년 정도 나눠 이전하고 싶습니다.", "00:34"),
            _line("PB", "위험 성향은 균형형으로 유지하되 세후 수익률을 중요하게 보시는 방향일까요?", "00:44"),
            _line("고객", "예금만으로는 물가를 못 따라갈 것 같아서 연 8% 정도는 기대하지만, 원금 변동이 너무 크면 부담스럽습니다.", "00:52"),
            _line("PB", "미국 배당주와 장기채를 일부 섞고, 금리 상승과 환율 변동 스트레스 테스트까지 같이 보겠습니다.", "01:06"),
        ],
        "ips_json": {
            "Goal": "자녀 전세자금 3억 확보 및 10년 장기 증여 계획",
            "Asset": 18,
            "Return": 8,
            "Risk": "균형형",
            "Time": 10,
            "Tax": "증여세, 금융소득종합과세, 해외주식 배당세",
            "Liquidity": "중간",
            "Legal": "증여 신고와 자금 출처 소명 필요",
            "Unique": "전세자금 3억은 단기 유동성으로 분리, 미국 배당주와 장기채 선호",
        },
    },
    {
        "customer_name": "김성삼",
        "seed_key": "kim-02-bond-ladder",
        "topic": "저쿠폰채와 만기 분산 전략",
        "transcript_json": [
            _line("PB", "지난번에 말씀하신 안정 자금 3억 원을 채권으로 운용하는 방안을 보겠습니다.", "00:01"),
            _line("고객", "예금 금리가 내려갈 수 있다고 해서 채권을 보고 있는데, 금리가 더 오르면 손실이 날까 봐 걱정입니다.", "00:10"),
            _line("PB", "전액 장기채보다 만기를 6개월, 1년, 2년으로 나누면 금리 변동 부담을 줄일 수 있습니다.", "00:23"),
            _line("고객", "세금 측면에서는 저쿠폰채가 유리하다고 들었습니다. 매매차익이 어떻게 처리되는지도 궁금합니다.", "00:35"),
            _line("PB", "개인 채권 매매차익은 비과세 가능성이 있어 이자 과세 비중을 낮추는 구조를 검토할 수 있습니다.", "00:46"),
            _line("고객", "그럼 원금 안정성이 높은 자금은 만기 분산 채권으로 두고 싶습니다. 필요하면 중간에 현금화도 가능해야 합니다.", "00:58"),
            _line("PB", "유동성은 중간 이상으로 유지하고, 목표 수익률은 안정 자금 기준 연 4% 안팎으로 보수적으로 잡겠습니다.", "01:12"),
        ],
        "ips_json": {
            "Goal": "전세자금 목적의 안정 자금 3억 원 만기 분산 운용",
            "Asset": 18,
            "Return": 4,
            "Risk": "안정형",
            "Time": 2,
            "Tax": "채권 이자소득세, 저쿠폰채 절세 효과",
            "Liquidity": "높음",
            "Legal": "채권 매매차익 과세 여부 확인",
            "Unique": "6개월, 1년, 2년 만기 분산과 중도 현금화 가능성 중시",
        },
    },
    {
        "customer_name": "김성삼",
        "seed_key": "kim-03-us-dividend",
        "topic": "미국 배당주와 환율 리스크 관리",
        "transcript_json": [
            _line("PB", "오늘은 장기 자금 중 미국 배당주 비중을 어느 정도 둘지 논의해 보겠습니다.", "00:01"),
            _line("고객", "달러 자산을 일부 갖고 싶습니다. 다만 환율이 지금 높은 편이면 나중에 손실이 날 수도 있지 않나요?", "00:10"),
            _line("PB", "맞습니다. 그래서 일시에 환전하기보다 분할 매수하고, 환율 하락 시나리오를 같이 계산하는 편이 좋습니다.", "00:24"),
            _line("고객", "배당을 받으면 세금도 있겠죠. 세후 현금흐름이 실제로 얼마나 남는지 보고 싶습니다.", "00:36"),
            _line("PB", "미국 원천징수와 국내 금융소득 합산 가능성을 반영해서 세후 배당수익률을 비교하겠습니다.", "00:47"),
            _line("고객", "성장주보다 변동성이 낮은 배당주 중심이면 좋겠습니다. 그래도 장기 물가 상승률은 이겨야 합니다.", "00:59"),
            _line("PB", "배당주 비중은 장기 자금의 일부로 제한하고, 국내 채권과 현금성 자산으로 변동성을 완충하겠습니다.", "01:12"),
        ],
        "ips_json": {
            "Goal": "달러 배당 현금흐름 확보와 장기 실질 구매력 방어",
            "Asset": 18,
            "Return": 7,
            "Risk": "균형형",
            "Time": 10,
            "Tax": "미국 배당 원천징수, 금융소득종합과세",
            "Liquidity": "중간",
            "Legal": "해외주식 배당소득 신고 검토",
            "Unique": "환율 분할 매수와 세후 배당수익률 비교 필요",
        },
    },
    {
        "customer_name": "김성삼",
        "seed_key": "kim-04-pension-isa",
        "topic": "연금계좌와 ISA 절세 한도 활용",
        "transcript_json": [
            _line("PB", "증여와 별도로 고객님 본인의 절세 계좌 활용 현황을 확인하겠습니다.", "00:01"),
            _line("고객", "연금저축과 IRP는 조금씩 넣고 있는데 한도를 꽉 채우지는 않았습니다. ISA도 만기가 다가옵니다.", "00:11"),
            _line("PB", "연금계좌는 세액공제와 과세이연 효과가 있고, ISA 만기 자금은 연금계좌 이전도 검토할 수 있습니다.", "00:25"),
            _line("고객", "다만 자금이 너무 오래 묶이는 것은 싫습니다. 전세자금이나 가족 행사로 현금이 필요할 수 있습니다.", "00:38"),
            _line("PB", "필수 유동성은 별도로 남기고, 장기 목적 자금만 절세 계좌에 배치하는 방식이 맞겠습니다.", "00:50"),
            _line("고객", "절세 효과가 숫자로 얼마나 되는지 보여주시면 좋겠습니다. 단순히 세금이 줄어든다는 말로는 판단하기 어렵습니다.", "01:01"),
            _line("PB", "납입 한도별 세액공제, 과세이연 효과, 중도 인출 제약을 함께 비교해 드리겠습니다.", "01:15"),
        ],
        "ips_json": {
            "Goal": "연금계좌와 ISA를 활용한 세후 수익률 개선",
            "Asset": 18,
            "Return": 6,
            "Risk": "균형형",
            "Time": 7,
            "Tax": "연금계좌 세액공제, ISA 비과세와 분리과세",
            "Liquidity": "중간",
            "Legal": "연금계좌 중도 인출 제한과 ISA 의무가입 기간 확인",
            "Unique": "필수 유동성은 별도 보유하고 장기 자금만 절세 계좌 활용",
        },
    },
    {
        "customer_name": "김성삼",
        "seed_key": "kim-05-family-governance",
        "topic": "가족 자금 이전과 증여 실행 순서",
        "transcript_json": [
            _line("PB", "오늘은 자녀에게 자금을 이전할 때 실행 순서와 기록 관리까지 정리해 보겠습니다.", "00:01"),
            _line("고객", "증여 신고를 빠뜨리거나 자금 출처가 불명확해지는 상황은 피하고 싶습니다.", "00:11"),
            _line("PB", "증여 시점, 금액, 계좌 이체 내역, 신고 자료를 한 묶음으로 관리하는 것이 중요합니다.", "00:23"),
            _line("고객", "자녀가 아직 투자 경험이 많지 않아서 한 번에 큰돈을 넘기면 운용을 잘 못할까 걱정도 됩니다.", "00:34"),
            _line("PB", "그렇다면 매년 일정 금액을 이전하고, 이전된 자금은 위험도가 낮은 포트폴리오부터 시작하는 방식이 적합합니다.", "00:47"),
            _line("고객", "저는 세금도 중요하지만 가족 간 분쟁 없이 투명하게 진행되는 것이 더 중요합니다.", "01:00"),
            _line("PB", "증여 실행 캘린더와 자녀 명의 운용 원칙을 함께 만들고, 필요 시 세무 전문가 검토를 연결하겠습니다.", "01:12"),
        ],
        "ips_json": {
            "Goal": "가족 간 분쟁 없는 단계적 증여 실행",
            "Asset": 18,
            "Return": 5,
            "Risk": "안정형",
            "Time": 10,
            "Tax": "증여세, 금융소득세",
            "Liquidity": "중간",
            "Legal": "증여 신고, 자금 출처 증빙, 가족 간 분쟁 예방",
            "Unique": "증여 실행 캘린더와 자녀 명의 보수적 운용 원칙 필요",
        },
    },
    {
        "customer_name": "이사조",
        "seed_key": "lee-01-startup-liquidity",
        "topic": "창업 자금 마련과 단기 유동성 관리",
        "transcript_json": [
            _line("PB", "이사조 고객님, 창업 자금 계획과 현재 투자 포지션을 함께 점검하겠습니다.", "00:01"),
            _line("고객", "1년 안에 창업 자금으로 10억 원 정도가 필요합니다. 전체 금융자산은 30억 원 정도이고 공격적으로 운용해 왔습니다.", "00:10"),
            _line("PB", "필수 창업 자금은 변동성 자산에서 분리해야 합니다. 10억 원은 현금성 또는 단기채로 보전하는 편이 안전합니다.", "00:25"),
            _line("고객", "수익 기회를 놓치는 건 아쉽지만, 창업 일정이 밀리면 안 됩니다. 나머지 자금은 AI와 반도체 섹터를 계속 보고 싶습니다.", "00:38"),
            _line("PB", "그러면 10억 원은 유동성 포켓, 나머지 20억 원은 고위험 성장 포켓으로 나누겠습니다.", "00:52"),
            _line("고객", "목표 수익률은 높게 보고 싶습니다. 다만 창업 자금만큼은 절대 크게 흔들리면 안 됩니다.", "01:03"),
            _line("PB", "두 포켓을 분리해 창업 자금의 손실 가능성과 성장 포켓의 최대 낙폭을 각각 보여드리겠습니다.", "01:15"),
        ],
        "ips_json": {
            "Goal": "1년 내 창업 자금 10억 원 확보와 성장 투자 병행",
            "Asset": 30,
            "Return": 20,
            "Risk": "공격형",
            "Time": 1,
            "Tax": "해외주식 양도세, 금융소득종합과세",
            "Liquidity": "높음",
            "Legal": "창업 법인 설립 자금 출처 증빙",
            "Unique": "창업 자금 10억은 단기 안전자산으로 분리, AI와 반도체 섹터 선호",
        },
    },
    {
        "customer_name": "이사조",
        "seed_key": "lee-02-ai-concentration",
        "topic": "AI 섹터 집중 투자 리스크 점검",
        "transcript_json": [
            _line("PB", "현재 AI 관련 종목 비중이 높아 포트폴리오 집중도를 점검해 보겠습니다.", "00:01"),
            _line("고객", "미국 AI 소프트웨어와 반도체 장비주 비중이 큽니다. 단기 변동성은 감수할 수 있습니다.", "00:10"),
            _line("PB", "감수 가능하더라도 특정 섹터와 환율이 동시에 흔들리면 손실 폭이 커질 수 있습니다.", "00:23"),
            _line("고객", "맞습니다. 하지만 너무 분산하면 수익률이 낮아질까 봐 걱정입니다.", "00:34"),
            _line("PB", "핵심 성장 포지션은 유지하되, 일부는 현금과 단기채로 헤지해 재진입 여력을 만드는 방식이 있습니다.", "00:45"),
            _line("고객", "좋습니다. 대신 상승장에서 너무 뒤처지지 않게 비중을 조절해 주세요.", "00:58"),
            _line("PB", "AI 섹터 30% 하락, 원달러 10% 하락, 금리 상승 시나리오를 같이 놓고 최대 낙폭을 계산하겠습니다.", "01:09"),
        ],
        "ips_json": {
            "Goal": "AI 섹터 성장 노출 유지와 집중 리스크 통제",
            "Asset": 30,
            "Return": 25,
            "Risk": "공격형",
            "Time": 3,
            "Tax": "해외주식 양도세, 손익통산",
            "Liquidity": "중간",
            "Legal": "해외주식 양도소득 신고",
            "Unique": "AI와 반도체 집중도가 높고 현금 재진입 여력 확보 필요",
        },
    },
    {
        "customer_name": "이사조",
        "seed_key": "lee-03-tax-loss-harvest",
        "topic": "해외주식 손익통산과 절세 매도 전략",
        "transcript_json": [
            _line("PB", "올해 해외주식 실현손익을 확인해서 양도세 절세 가능성을 보겠습니다.", "00:01"),
            _line("고객", "수익 난 종목도 있고 손실 중인 종목도 있습니다. 연말 전에 정리하면 세금이 줄어들까요?", "00:11"),
            _line("PB", "같은 해 해외주식 양도차익과 차손은 통산 가능하므로 손실 종목 매도 시점을 검토할 수 있습니다.", "00:25"),
            _line("고객", "다만 장기적으로 좋게 보는 종목은 팔고 싶지 않습니다. 다시 사도 되는지도 궁금합니다.", "00:38"),
            _line("PB", "투자 판단과 세무 처리를 분리해서 봐야 합니다. 매도 후 재매수 시 가격 변동과 신고 자료를 함께 관리해야 합니다.", "00:51"),
            _line("고객", "올해는 절세도 중요하지만 포트폴리오 방향을 망치고 싶지는 않습니다.", "01:04"),
            _line("PB", "실현손익, 기본공제, 환율을 반영해 세금 절감액과 포지션 유지 비용을 비교하겠습니다.", "01:16"),
        ],
        "ips_json": {
            "Goal": "해외주식 손익통산을 활용한 연말 절세",
            "Asset": 30,
            "Return": 18,
            "Risk": "공격형",
            "Time": 1,
            "Tax": "해외주식 양도세, 기본공제, 손익통산",
            "Liquidity": "낮음",
            "Legal": "해외주식 양도소득세 신고와 거래 증빙",
            "Unique": "손실 종목 절세 매도 후 핵심 포지션 재구축 여부 검토",
        },
    },
    {
        "customer_name": "이사조",
        "seed_key": "lee-04-structured-note",
        "topic": "고위험 ELS와 대체 투자 편입 검토",
        "transcript_json": [
            _line("PB", "공격형 포트폴리오 안에서 ELS나 사모 대체 투자 편입 가능성을 보겠습니다.", "00:01"),
            _line("고객", "쿠폰이 높은 상품이 있으면 관심은 있습니다. 다만 원금 손실 조건은 정확히 알고 싶습니다.", "00:10"),
            _line("PB", "녹인 조건, 기초자산 상관관계, 조기상환 실패 시 손실 구간을 먼저 확인해야 합니다.", "00:23"),
            _line("고객", "저는 단기 수익률이 중요하지만 자금이 오래 묶이는 건 싫습니다. 창업 때문에 현금이 필요할 수 있습니다.", "00:36"),
            _line("PB", "그렇다면 비중은 제한하고, 만기와 중도 환매 가능성을 유동성 조건에 반영하겠습니다.", "00:48"),
            _line("고객", "좋습니다. 기대수익률만 보지 말고 최악의 경우 손실도 같이 보여주세요.", "00:59"),
            _line("PB", "기초지수 20%, 30%, 40% 하락 시 손실 구간과 전체 포트폴리오 영향도를 산출하겠습니다.", "01:10"),
        ],
        "ips_json": {
            "Goal": "공격형 포트폴리오의 쿠폰 수익 강화",
            "Asset": 30,
            "Return": 15,
            "Risk": "공격형",
            "Time": 2,
            "Tax": "파생결합증권 배당소득 과세",
            "Liquidity": "낮음",
            "Legal": "고난도 금융투자상품 적합성 확인",
            "Unique": "창업 자금 수요 때문에 비중 제한과 중도 환매 조건 확인 필요",
        },
    },
    {
        "customer_name": "이사조",
        "seed_key": "lee-05-post-exit-plan",
        "topic": "스타트업 지분 매각 이후 자금 운용 계획",
        "transcript_json": [
            _line("PB", "향후 스타트업 지분 일부를 매각했을 때 들어올 자금 운용 계획을 미리 세워보겠습니다.", "00:01"),
            _line("고객", "투자가 성공하면 몇 년 안에 큰 현금이 생길 수 있습니다. 그때 세금과 재투자 방향이 걱정입니다.", "00:12"),
            _line("PB", "유동성 이벤트가 생기면 양도세, 법인 설립 구조, 개인 자금 운용을 동시에 검토해야 합니다.", "00:25"),
            _line("고객", "저는 다시 창업하거나 후속 투자에 넣을 가능성이 큽니다. 현금을 오래 놀리고 싶지는 않습니다.", "00:37"),
            _line("PB", "단기 대기 자금, 후속 투자 자금, 장기 보전 자금을 나눠야 합니다. 전액을 벤처 투자에 재투입하면 리스크가 큽니다.", "00:50"),
            _line("고객", "수익 기회는 잡되 한 번 번 돈을 크게 잃는 건 피하고 싶습니다.", "01:03"),
            _line("PB", "매각 시점별 세후 현금흐름과 재투자 한도를 시나리오로 만들어 보겠습니다.", "01:14"),
        ],
        "ips_json": {
            "Goal": "스타트업 지분 매각 후 세후 현금흐름과 재투자 계획 수립",
            "Asset": 30,
            "Return": 20,
            "Risk": "공격형",
            "Time": 5,
            "Tax": "비상장주식 양도세, 금융소득세",
            "Liquidity": "중간",
            "Legal": "비상장주식 양도 신고와 법인 투자 구조 검토",
            "Unique": "후속 창업과 벤처 재투자 의향이 높아 자금 포켓 분리 필요",
        },
    },
    {
        "customer_name": "박기업",
        "seed_key": "park-01-succession",
        "topic": "기업 승계와 상속 준비",
        "transcript_json": [
            _line("PB", "박기업 고객님, 오늘은 기업 승계와 상속 준비를 중심으로 정리하겠습니다.", "00:01"),
            _line("고객", "회사 지분과 부동산까지 합치면 자산 규모가 750억 원 정도 됩니다. 자녀 승계를 준비해야 하는데 세금이 가장 걱정입니다.", "00:11"),
            _line("PB", "기업상속공제 요건, 지분 이전 시점, 대표님 개인 유동성을 함께 봐야 합니다.", "00:27"),
            _line("고객", "회사를 급하게 넘기고 싶지는 않습니다. 다만 갑작스러운 상속세 납부 재원이 부족한 상황은 피하고 싶습니다.", "00:39"),
            _line("PB", "상속세 납부 재원은 보험, 배당 정책, 일부 금융자산 유동화로 사전에 마련할 수 있습니다.", "00:52"),
            _line("고객", "위험한 투자는 원하지 않습니다. 연 3% 정도라도 안정적으로 현금흐름이 나오면 좋겠습니다.", "01:04"),
            _line("PB", "안정형 포트폴리오와 승계 일정표를 연결해 세금 납부 재원과 회사 지배력을 동시에 점검하겠습니다.", "01:16"),
        ],
        "ips_json": {
            "Goal": "기업 승계와 상속세 납부 재원 사전 준비",
            "Asset": 750,
            "Return": 3,
            "Risk": "안정형",
            "Time": 10,
            "Tax": "상속세, 증여세, 종합소득세",
            "Liquidity": "높음",
            "Legal": "기업상속공제 요건과 지분 승계 절차",
            "Unique": "회사 지배력 유지와 상속세 납부 재원 확보가 핵심",
        },
    },
    {
        "customer_name": "박기업",
        "seed_key": "park-02-corporate-cash",
        "topic": "법인 운전자금 20억 유동성 운용",
        "transcript_json": [
            _line("PB", "법인 운전자금 20억 원은 언제든 사용할 수 있어야 한다고 하셨습니다.", "00:01"),
            _line("고객", "네, 원자재 결제와 인건비 때문에 3개월 안에 쓸 수도 있습니다. 손실이 나면 곤란합니다.", "00:10"),
            _line("PB", "그 자금은 수익률보다 원금 안정성과 즉시 유동성이 우선입니다. MMF, RP, 초단기채 위주로 보겠습니다.", "00:23"),
            _line("고객", "법인 자금이라 회계 처리와 내부 승인도 깔끔해야 합니다.", "00:35"),
            _line("PB", "상품별 만기, 중도 환매, 회계 증빙 자료를 같이 정리하겠습니다.", "00:45"),
            _line("고객", "수익률은 낮아도 괜찮습니다. 대신 현금이 묶이면 안 됩니다.", "00:56"),
            _line("PB", "운전자금은 별도 포켓으로 분리하고, 개인 장기 자산과 혼합하지 않는 기준을 제안드리겠습니다.", "01:06"),
        ],
        "ips_json": {
            "Goal": "법인 운전자금 20억 원의 원금 안정성과 즉시 유동성 확보",
            "Asset": 750,
            "Return": 3,
            "Risk": "안정형",
            "Time": 1,
            "Tax": "법인 이자수익 과세",
            "Liquidity": "높음",
            "Legal": "법인 자금 운용 내부 승인과 회계 증빙",
            "Unique": "3개월 내 사용 가능성이 높은 운전자금 20억 원은 별도 관리",
        },
    },
    {
        "customer_name": "박기업",
        "seed_key": "park-03-real-estate",
        "topic": "부동산 편중과 유동화 전략",
        "transcript_json": [
            _line("PB", "대표님 자산 중 부동산 비중이 높아 유동화 가능성을 점검해 보겠습니다.", "00:01"),
            _line("고객", "공장 부지와 임대 건물이 많습니다. 장부상 가치는 크지만 현금화가 쉽지 않습니다.", "00:11"),
            _line("PB", "상속세나 사업 자금 수요가 생겼을 때 부동산만으로는 납부 재원을 마련하기 어렵습니다.", "00:24"),
            _line("고객", "매각은 신중해야 합니다. 임대수익도 있고 가족들이 보유를 원합니다.", "00:35"),
            _line("PB", "전면 매각보다 담보 대출 한도, 일부 지분 증여, 리츠나 금융자산 대체를 비교해 볼 수 있습니다.", "00:47"),
            _line("고객", "세금과 가족 의견을 모두 고려해야 합니다. 급하게 팔아서 손해 보는 건 피하고 싶습니다.", "01:00"),
            _line("PB", "부동산별 유동화 난이도와 세후 현금화 금액을 표로 정리해 승계 계획에 반영하겠습니다.", "01:12"),
        ],
        "ips_json": {
            "Goal": "부동산 편중 완화와 상속세 납부 재원 확보",
            "Asset": 750,
            "Return": 3,
            "Risk": "안정형",
            "Time": 10,
            "Tax": "부동산 양도세, 종합부동산세, 상속세",
            "Liquidity": "중간",
            "Legal": "부동산 지분 증여와 담보 설정 검토",
            "Unique": "공장 부지와 임대 건물 비중이 높아 세후 유동화 금액 산출 필요",
        },
    },
    {
        "customer_name": "박기업",
        "seed_key": "park-04-dividend-policy",
        "topic": "오너 배당 정책과 금융소득 관리",
        "transcript_json": [
            _line("PB", "법인 이익을 대표님 개인 자산으로 이전하는 배당 정책도 점검하겠습니다.", "00:01"),
            _line("고객", "배당을 늘리면 개인 세금이 커질까 걱정입니다. 그래도 상속 재원은 개인 쪽에 있어야 합니다.", "00:11"),
            _line("PB", "배당소득은 금융소득종합과세와 종합소득세율 영향을 받습니다. 급격한 배당보다 연도별 분산이 중요합니다.", "00:25"),
            _line("고객", "가족 주주도 있어서 배당 정책을 갑자기 바꾸면 설명이 필요합니다.", "00:38"),
            _line("PB", "가족 주주별 세후 현금흐름과 회사 유보금 수준을 함께 봐야 합니다.", "00:49"),
            _line("고객", "회사 성장에 필요한 자금은 남겨야 합니다. 개인 상속 준비 때문에 회사가 약해지면 안 됩니다.", "01:00"),
            _line("PB", "배당, 급여, 퇴직금, 보험을 조합해 회사 재무 안정성과 개인 유동성을 동시에 맞추겠습니다.", "01:12"),
        ],
        "ips_json": {
            "Goal": "오너 개인 상속 재원 마련을 위한 배당 정책 설계",
            "Asset": 750,
            "Return": 3,
            "Risk": "안정형",
            "Time": 7,
            "Tax": "배당소득세, 금융소득종합과세, 종합소득세",
            "Liquidity": "높음",
            "Legal": "가족 주주 배당 정책과 이사회 승인 절차",
            "Unique": "회사 유보금과 개인 상속 재원 간 균형 필요",
        },
    },
    {
        "customer_name": "박기업",
        "seed_key": "park-05-family-office",
        "topic": "패밀리오피스형 자산관리 체계",
        "transcript_json": [
            _line("PB", "대표님 가문 전체 자산을 패밀리오피스 관점으로 관리하는 방안을 제안드립니다.", "00:01"),
            _line("고객", "개인, 법인, 배우자, 자녀 명의 자산이 섞여 있어 전체 현황을 한눈에 보기 어렵습니다.", "00:11"),
            _line("PB", "명의별 자산, 세금 이슈, 현금흐름, 승계 일정을 하나의 대시보드로 관리할 필요가 있습니다.", "00:24"),
            _line("고객", "저는 투자수익률보다도 가족들이 같은 자료를 보고 의사결정하는 체계를 만들고 싶습니다.", "00:36"),
            _line("PB", "가족 회의용 리포트, 투자 원칙서, 세무 일정표를 정기적으로 업데이트하는 구조가 적합합니다.", "00:49"),
            _line("고객", "민감한 정보가 많으니 접근 권한도 구분되어야 합니다.", "01:00"),
            _line("PB", "PB, 세무사, 가족 구성원별 열람 범위를 나누고, 주요 의사결정 기록을 남기는 방식으로 설계하겠습니다.", "01:11"),
        ],
        "ips_json": {
            "Goal": "가문 전체 자산의 통합 관리와 승계 의사결정 체계 구축",
            "Asset": 750,
            "Return": 3,
            "Risk": "안정형",
            "Time": 10,
            "Tax": "상속세, 증여세, 종합소득세, 법인세",
            "Liquidity": "높음",
            "Legal": "명의별 자산 권한, 개인정보 접근 통제, 가족 의사결정 기록",
            "Unique": "개인, 법인, 배우자, 자녀 명의 자산을 패밀리오피스 방식으로 통합 관리",
        },
    },
]


def _raw_note(item: DemoConsultation) -> str:
    lines = [
        f"[DEMO_SEED:{item['seed_key']}]",
        f"상담 주제: {item['topic']}",
    ]
    lines.extend(
        f"{row['utterance_time']} {row['speaker_role']}: {row['text']}"
        for row in item["transcript_json"]
    )
    return "\n".join(lines)


def _find_clients_by_name(supabase) -> dict[str, str]:
    names = sorted({item["customer_name"] for item in DEMO_CONSULTATIONS})
    result = (
        supabase.table("client")
        .select("id,name")
        .in_("name", names)
        .execute()
    )
    clients = {row["name"]: row["id"] for row in result.data or []}
    missing = [name for name in names if name not in clients]
    if missing:
        raise RuntimeError(f"client 테이블에 데모 고객이 없습니다: {', '.join(missing)}")
    return clients


def _already_seeded(supabase, seed_key: str) -> bool:
    marker = f"[DEMO_SEED:{seed_key}]"
    result = (
        supabase.table("consultation")
        .select("id")
        .ilike("raw_note", f"%{marker}%")
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _create_consultation(supabase, *, client_id: str, item: DemoConsultation) -> dict:
    snapshot_payload = build_ips_snapshot_payload(
        client_id=client_id,
        consultation_id=None,
        source_type="consultation",
        raw_ips_json=item["ips_json"],
    )
    payload = {
        "p_client_id": client_id,
        "p_raw_note": _raw_note(item),
        "p_transcript_json": item["transcript_json"],
        "p_ips_json": item["ips_json"],
        "p_goal": snapshot_payload["goal"],
        "p_asset": snapshot_payload["asset"],
        "p_return": snapshot_payload["return"],
        "p_risk": snapshot_payload["risk"],
        "p_time": snapshot_payload["time"],
        "p_tax": snapshot_payload["tax"],
        "p_liquidity": snapshot_payload["liquidity"],
        "p_legal": snapshot_payload["legal"],
        "p_unique": snapshot_payload["unique"],
        "p_raw_ips_json": snapshot_payload["raw_ips_json"],
    }
    result = (
        supabase.rpc("create_stt_consultation_with_snapshot", payload)
        .execute()
    )
    rows = result.data or []
    if not rows:
        raise RuntimeError(f"상담 생성 RPC 응답이 비어 있습니다: {item['seed_key']}")
    return rows[0]


def seed(*, dry_run: bool = False) -> None:
    grouped: dict[str, list[DemoConsultation]] = {}
    for item in DEMO_CONSULTATIONS:
        grouped.setdefault(item["customer_name"], []).append(item)

    if dry_run:
        print("=== 데모 상담 시드 계획 ===")
        for name, items in grouped.items():
            print(f"{name}: {len(items)}건")
            for item in items:
                print(f"  - {item['seed_key']}: {item['topic']}")
        print(f"총 {len(DEMO_CONSULTATIONS)}건")
        return

    supabase = get_supabase()
    clients = _find_clients_by_name(supabase)

    created_count = 0
    skipped_count = 0
    print("=== 데모 상담 시드 시작 ===")
    for item in DEMO_CONSULTATIONS:
        name = item["customer_name"]
        if _already_seeded(supabase, item["seed_key"]):
            skipped_count += 1
            print(f"SKIP {name} / {item['topic']} ({item['seed_key']})")
            continue

        created = _create_consultation(
            supabase,
            client_id=clients[name],
            item=item,
        )
        created_count += 1
        print(
            "CREATED "
            f"{name} / {item['topic']} "
            f"consultation={created['consultation_id']} "
            f"ips_snapshot={created.get('ips_snapshot_id')}"
        )

    print("=" * 48)
    print(f"생성: {created_count}건, 건너뜀: {skipped_count}건")
    print("=" * 48)


def verify() -> None:
    supabase = get_supabase()
    clients = _find_clients_by_name(supabase)
    expected_keys = {
        item["seed_key"]: item
        for item in DEMO_CONSULTATIONS
    }

    consultations_by_customer = {
        name: []
        for name in clients
    }
    consultation_ids: list[str] = []
    for seed_key, item in expected_keys.items():
        marker = f"[DEMO_SEED:{seed_key}]"
        result = (
            supabase.table("consultation")
            .select("id,client_id,raw_note")
            .ilike("raw_note", f"%{marker}%")
            .execute()
        )
        rows = result.data or []
        consultations_by_customer[item["customer_name"]].extend(rows)
        consultation_ids.extend(row["id"] for row in rows)

    snapshot_ids: set[str] = set()
    if consultation_ids:
        snapshot_result = (
            supabase.table("ips_snapshot")
            .select("consultation_id")
            .eq("source_type", "consultation")
            .in_("consultation_id", consultation_ids)
            .execute()
        )
        snapshot_ids = {
            row["consultation_id"]
            for row in snapshot_result.data or []
        }

    print("=== 데모 상담 시드 검증 ===")
    total_consultations = 0
    total_snapshots = 0
    for name in sorted(consultations_by_customer):
        rows = consultations_by_customer[name]
        customer_snapshot_count = sum(1 for row in rows if row["id"] in snapshot_ids)
        total_consultations += len(rows)
        total_snapshots += customer_snapshot_count
        print(
            f"{name}: consultation {len(rows)}건, "
            f"ips_snapshot(source_type=consultation) {customer_snapshot_count}건"
        )
    print(f"총 consultation {total_consultations}건, ips_snapshot {total_snapshots}건")

    if total_consultations != len(DEMO_CONSULTATIONS) or total_snapshots != len(DEMO_CONSULTATIONS):
        raise RuntimeError("데모 상담 seed 검증 실패")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 쓰지 않고 생성 대상만 출력합니다.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="DB에 생성된 데모 상담과 consultation 타입 IPS 스냅샷 개수를 검증합니다.",
    )
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
