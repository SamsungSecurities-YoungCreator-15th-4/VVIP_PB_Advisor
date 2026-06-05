import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI


load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

INPUT_FILE = "customer_text.txt"
OUTPUT_FILE = "goal_rrttllu_result.json"


GOAL_RRTTLLU_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "Goal": {
            "type": ["string", "null"],
            "description": "고객의 핵심 재무/투자 목표. 상담과 무관하거나 언급이 없으면 null."
        },
        "Asset": {
            "type": ["number", "null"],
            "description": "운용 또는 보유 자산 규모. 단위는 억 원. 예: 15억 원이면 15."
        },
        "Return": {
            "type": ["number", "null"],
            "description": "목표 수익률. 단위는 %. 예: 연 5%면 5."
        },
        "Risk": {
            "type": ["string", "null"],
            "enum": ["안정형", "균형형", "공격형", None],
            "description": "고객의 위험 성향. 안정형/균형형/공격형 중 하나. 언급이 없으면 null."
        },
        "Time": {
            "type": ["number", "null"],
            "description": "투자 기간. 단위는 년. 예: 10년이면 10."
        },
        "Tax": {
            "type": ["string", "null"],
            "description": "세금 관련 이슈. 예: 증여세, 상속세, 양도소득세, 배당소득세 등. 언급 없으면 null."
        },
        "Liquidity": {
            "type": ["string", "null"],
            "enum": ["낮음", "중간", "높음", None],
            "description": "유동성 필요 수준. 단기 현금 필요가 크면 높음, 일부 필요하면 중간, 거의 없으면 낮음."
        },
        "Legal": {
            "type": ["string", "null"],
            "description": "법률/규제/계약 관련 제약. 언급 없으면 null."
        },
        "Unique": {
            "type": ["string", "null"],
            "description": "고객의 특수 니즈. 예: 자녀 전세자금, 증여 계획, 미국 배당주 선호, 장기채 선호 등."
        }
    },
    "required": [
        "Goal",
        "Asset",
        "Return",
        "Risk",
        "Time",
        "Tax",
        "Liquidity",
        "Legal",
        "Unique"
    ]
}


def validate_env():
    required_vars = {
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
        "AZURE_OPENAI_DEPLOYMENT": AZURE_OPENAI_DEPLOYMENT,
    }

    missing = [key for key, value in required_vars.items() if not value]

    if missing:
        raise ValueError(f".env에 다음 값이 없습니다: {', '.join(missing)}")


def load_customer_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"고객 발화 파일을 찾을 수 없습니다: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        raise ValueError("customer_text.txt가 비어 있습니다.")

    return text


def get_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def extract_goal_rrttllu(customer_text: str) -> dict:
    client = get_client()

    system_prompt = """
너는 PB 상담 스크립트에서 고객의 투자 목적과 RRTTLLU 정보를 추출하는 금융 상담 정보 추출기다.

반드시 다음 규칙을 따른다.

1. 고객 발화에서 명시적으로 드러난 내용만 추출한다.
2. 추측하지 않는다.
3. 언급되지 않은 항목은 null로 둔다.
4. 고객 발화가 PB-고객 금융 상담과 관련 없는 내용이면 모든 key 값을 null로 둔다.
5. 숫자는 정규화한다.
   - Asset은 억 원 단위 숫자로 변환한다. 예: 15억 원 → 15, 3억 원 → 3
   - Return은 % 단위 숫자로 변환한다. 예: 연 5% → 5
   - Time은 년 단위 숫자로 변환한다. 예: 10년 → 10, 18개월 → 1.5
6. Risk는 반드시 안정형, 균형형, 공격형 중 하나 또는 null이다.
   - 원금보전, 예금, 채권 위주, 손실 회피 → 안정형
   - 배당주, 채권+주식 혼합, 중간 수준 위험 → 균형형
   - 고수익, 성장주, 레버리지, 적극 투자 → 공격형
7. Liquidity는 반드시 낮음, 중간, 높음 중 하나 또는 null이다.
   - 단기 자금 인출 필요 또는 생활/전세/사업 자금 필요 → 높음
   - 일부 자금 필요 가능성 → 중간
   - 장기 운용 가능하고 단기 인출 언급 없음 → 낮음
"""

    user_prompt = f"""
아래 고객 발화에서 Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique를 추출해라.

고객 발화:
{customer_text}
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "goal_rrttllu_extraction",
                    "strict": True,
                    "schema": GOAL_RRTTLLU_SCHEMA,
                },
            },
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("모델 응답이 비어 있습니다.")

        return json.loads(content)

    except json.JSONDecodeError as e:
        raise ValueError(f"모델 응답을 JSON으로 파싱하지 못했습니다: {e}")

    except Exception as e:
        raise RuntimeError(f"Azure OpenAI 호출 중 오류가 발생했습니다: {e}")


def save_result(result: dict, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def main():
    validate_env()

    customer_text = load_customer_text(INPUT_FILE)

    result = extract_goal_rrttllu(customer_text)

    save_result(result, OUTPUT_FILE)

    print("Goal + RRTTLLU 추출 완료")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n저장 완료: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()