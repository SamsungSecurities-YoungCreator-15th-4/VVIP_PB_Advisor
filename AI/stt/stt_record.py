import argparse
import json
import os
import time
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
from openai import AzureOpenAI


load_dotenv()

SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

DEFAULT_AUDIO_DIR = "audio"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
MAPPED_TRANSCRIPT_OUTPUT_FILE = "mapped_transcript.json"
GOAL_RRTTLLU_OUTPUT_FILE = "goal_rrttllu_result.json"
TICKS_PER_SECOND = 10_000_000

SPEAKER_ROLE_MAP = {
    "Guest-1": "PB",
    "Guest-2": "고객",
}

GOAL_RRTTLLU_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "Goal": {
            "type": ["string", "null"],
            "description": "고객의 핵심 재무/투자 목표. 상담과 무관하거나 언급이 없으면 null.",
        },
        "Asset": {
            "type": ["number", "null"],
            "description": "운용 또는 보유 자산 규모. 단위는 억 원. 예: 15억 원이면 15.",
        },
        "Return": {
            "type": ["number", "null"],
            "description": "목표 수익률. 단위는 %. 예: 연 5%면 5.",
        },
        "Risk": {
            "type": ["string", "null"],
            "enum": ["안정형", "균형형", "공격형", None],
            "description": "고객의 위험 성향. 안정형/균형형/공격형 중 하나. 언급이 없으면 null.",
        },
        "Time": {
            "type": ["number", "null"],
            "description": "투자 기간. 단위는 년. 예: 10년이면 10.",
        },
        "Tax": {
            "type": ["string", "null"],
            "description": "세금 관련 이슈. 예: 증여세, 상속세, 양도소득세, 배당소득세 등. 언급 없으면 null.",
        },
        "Liquidity": {
            "type": ["string", "null"],
            "enum": ["낮음", "중간", "높음", None],
            "description": "유동성 필요 수준. 단기 현금 필요가 크면 높음, 일부 필요하면 중간, 거의 없으면 낮음.",
        },
        "Legal": {
            "type": ["string", "null"],
            "description": "법률/규제/계약 관련 제약. 언급 없으면 null.",
        },
        "Unique": {
            "type": ["string", "null"],
            "description": "고객의 특수 니즈. 예: 자녀 전세자금, 증여 계획, 미국 배당주 선호, 장기채 선호 등.",
        },
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
        "Unique",
    ],
}


def validate_env():
    required_vars = {
        "AZURE_SPEECH_KEY": SPEECH_KEY,
        "AZURE_SPEECH_REGION": SPEECH_REGION,
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
        "AZURE_OPENAI_DEPLOYMENT": AZURE_OPENAI_DEPLOYMENT,
    }

    missing = [key for key, value in required_vars.items() if not value]

    if missing:
        raise ValueError(f".env에 다음 값이 없습니다: {', '.join(missing)}")


def find_latest_wav_file(audio_dir: str) -> str:
    audio_path = Path(audio_dir)

    if not audio_path.exists():
        raise FileNotFoundError(f"음성 파일 폴더를 찾을 수 없습니다: {audio_dir}")

    if not audio_path.is_dir():
        raise NotADirectoryError(f"음성 파일 경로가 폴더가 아닙니다: {audio_dir}")

    audio_files = [
        path
        for path in audio_path.iterdir()
        if path.is_file() and path.suffix.lower() == ".wav"
    ]

    if not audio_files:
        raise FileNotFoundError(f"{audio_dir} 폴더에 전사할 WAV 파일이 없습니다.")

    return str(max(audio_files, key=lambda path: path.stat().st_mtime_ns))


def transcribe_with_diarization(audio_file_path: str) -> list[dict]:
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {audio_file_path}")

    speech_config = speechsdk.SpeechConfig(
        subscription=SPEECH_KEY,
        region=SPEECH_REGION,
    )
    speech_config.speech_recognition_language = "ko-KR"

    audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    results = []
    done = False
    cancellation_error = None

    def transcribed_handler(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            speaker_id = evt.result.speaker_id
            text = evt.result.text

            if text:
                item = {
                    "sequence": len(results) + 1,
                    "speaker_label": speaker_id,
                    "speaker_role": None,
                    "text": text,
                    "offset_ticks": evt.result.offset,
                    "duration_ticks": evt.result.duration,
                }
                results.append(item)
                print(f"{speaker_id}: {text}")

        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("인식된 음성이 없습니다.")

    def canceled_handler(evt):
        nonlocal done, cancellation_error
        print(f"취소됨: {evt}")

        result = getattr(evt, "result", None)
        cancellation_details = getattr(evt, "cancellation_details", None)

        if not cancellation_details and result:
            cancellation_details = getattr(result, "cancellation_details", None)

        reason = (
            getattr(cancellation_details, "reason", None)
            if cancellation_details
            else getattr(evt, "reason", None)
        )

        if reason == speechsdk.CancellationReason.Error:
            error_details = (
                getattr(cancellation_details, "error_details", None)
                if cancellation_details
                else getattr(evt, "error_details", None)
            )
            error_code = (
                getattr(cancellation_details, "error_code", None)
                if cancellation_details
                else getattr(evt, "error_code", None)
            )
            detail_parts = [
                str(part)
                for part in [error_code, error_details]
                if part
            ]
            detail_message = " / ".join(detail_parts) or "상세 오류 없음"
            cancellation_error = RuntimeError(
                f"STT 전사가 오류로 취소되었습니다: {detail_message}"
            )

        done = True

    def session_stopped_handler(evt):
        nonlocal done
        print("세션 종료")
        done = True

    transcriber.transcribed.connect(transcribed_handler)
    transcriber.canceled.connect(canceled_handler)
    transcriber.session_stopped.connect(session_stopped_handler)

    print("1/5 STT + 화자 분리 시작...")
    transcriber.start_transcribing_async().get()

    try:
        while not done:
            time.sleep(0.5)
    finally:
        # 루프 중 예외(KeyboardInterrupt 등)가 나도 세션을 반드시 종료해 리소스 누수 방지.
        # 종료 호출 자체의 예외는 원래 예외를 덮어쓰지 않도록 잡아서 로그만 남긴다.
        try:
            transcriber.stop_transcribing_async().get()
        except Exception as cleanup_error:
            print(f"STT 세션 종료 중 오류 발생: {cleanup_error}")

    if cancellation_error:
        raise cancellation_error

    return results


def format_ticks_as_mmss(ticks: int | None) -> str:
    if ticks is None:
        return "00:00"

    total_seconds = int(ticks / TICKS_PER_SECOND)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def map_speaker_roles(transcript: list[dict]) -> list[dict]:
    print("2/5 화자 역할 매핑 시작...")

    mapped_result = []

    for item in transcript:
        speaker_label = item.get("speaker_label")
        speaker_role = SPEAKER_ROLE_MAP.get(speaker_label, "Unknown")
        text = item.get("text", "")

        if mapped_result and mapped_result[-1]["speaker_role"] == speaker_role:
            mapped_result[-1]["text"] = " ".join(
                part for part in [mapped_result[-1]["text"], text] if part
            )
            continue

        mapped_result.append(
            {
                "speaker_role": speaker_role,
                "text": text,
                "utterance_time": format_ticks_as_mmss(item.get("offset_ticks")),
            }
        )

    return mapped_result


def extract_customer_text(mapped_transcript: list[dict]) -> str:
    print("3/5 고객 발화 추출 시작...")

    customer_texts = [
        f"[{item.get('utterance_time', '00:00')}] {item['text']}"
        for item in mapped_transcript
        if item.get("speaker_role") == "고객"
    ]

    return "\n".join(customer_texts)


def get_openai_client() -> AzureOpenAI:
    validate_env()
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def extract_goal_rrttllu(customer_text: str) -> dict:
    print("4/5 Goal + RRTTLLU JSON 구조화 시작...")

    if not customer_text.strip():
        raise ValueError("고객 발화가 비어 있어 Goal/RRTTLLU를 추출할 수 없습니다.")

    client = get_openai_client()

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
8. 고객 발화는 시간순이며 각 줄의 [MM:SS]는 발화 시작 시각이다.
   - 같은 항목이 여러 번 언급되거나 정정되면 가장 마지막 발화의 값을 최종값으로 채택한다.
   - 한 발화 안에서 같은 항목이 여러 번 나오면 문장 안에서 더 뒤에 나온 값을 최종값으로 채택한다.
"""

    user_prompt = f"""
아래 시간순 고객 발화에서 Goal, Asset, Return, Risk, Time, Tax, Liquidity, Legal, Unique를 추출해라.

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
    except Exception as e:
        raise RuntimeError(f"Azure OpenAI 호출 중 오류가 발생했습니다: {e}") from e

    if not response.choices:
        raise ValueError("모델 응답의 choices가 비어 있습니다.")

    content = response.choices[0].message.content

    if not content:
        raise ValueError("모델 응답이 비어 있습니다.")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"모델 응답을 JSON으로 파싱하지 못했습니다: {e}") from e


def save_json(data, output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {output_path}")


def run_pipeline(audio_dir: str, output_dir: str | Path):
    validate_env()

    audio_file_path = find_latest_wav_file(audio_dir)
    print(f"전사 대상 음성 파일: {audio_file_path}")
    output_path = Path(output_dir)

    transcript = transcribe_with_diarization(audio_file_path)

    mapped_transcript = map_speaker_roles(transcript)
    mapped_transcript_output = output_path / MAPPED_TRANSCRIPT_OUTPUT_FILE
    save_json(mapped_transcript, mapped_transcript_output)

    customer_text = extract_customer_text(mapped_transcript)

    goal_rrttllu = extract_goal_rrttllu(customer_text)
    goal_rrttllu_output = output_path / GOAL_RRTTLLU_OUTPUT_FILE
    save_json(goal_rrttllu, goal_rrttllu_output)

    print("5/5 STT 통합 파이프라인 완료")
    print(f"출력 파일: {mapped_transcript_output}, {goal_rrttllu_output}")
    print(json.dumps(goal_rrttllu, ensure_ascii=False, indent=2))


def parse_args():
    parser = argparse.ArgumentParser(
        description="음성 전사, 화자 분리, 화자 매핑, 고객 발화 추출, Goal/RRTTLLU JSON 구조화를 한 번에 실행합니다."
    )
    parser.add_argument(
        "--audio-dir",
        default=DEFAULT_AUDIO_DIR,
        help=f"전사할 음성 파일이 들어 있는 폴더 경로. 기본값: {DEFAULT_AUDIO_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"결과 JSON을 저장할 폴더 경로. 기본값: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(args.audio_dir, args.output_dir)
