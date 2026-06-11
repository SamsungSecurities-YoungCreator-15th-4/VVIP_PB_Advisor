from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import UploadFile

from app.core.config import STT_AUDIO_DIR, STT_OUTPUT_DIR

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class SttPipelineResult:
    transcript_json: list[dict]
    ips_json: dict
    transcript_title: str
    ips_title: str
    transcript_output_path: Path
    ips_output_path: Path


def run_uploaded_wav_pipeline(
    *,
    customer_name: str,
    audio_file: UploadFile,
) -> SttPipelineResult:
    if not audio_file.filename:
        raise ValueError("음성 파일명이 비어 있습니다.")

    if Path(audio_file.filename).suffix.lower() != ".wav":
        raise ValueError("WAV 형식의 음성 파일만 업로드할 수 있습니다.")

    STT_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    upload_filename = f"{datetime.now(KST):%Y%m%d%H%M%S%f}_{uuid4().hex}.wav"
    upload_path = STT_AUDIO_DIR / upload_filename

    try:
        _save_upload_file(audio_file, upload_path)
        transcript_json, ips_json = run_stt_pipeline(str(upload_path))
        title_prefix = f"{datetime.now(KST):%y%m%d}_{customer_name}"
        transcript_title = f"{title_prefix}_상담 스크립트"
        ips_title = f"{title_prefix}_ips"
        transcript_output_path = STT_OUTPUT_DIR / f"{transcript_title}.json"
        ips_output_path = STT_OUTPUT_DIR / f"{ips_title}.json"

        _save_json(transcript_json, transcript_output_path)
        _save_json(ips_json, ips_output_path)

        return SttPipelineResult(
            transcript_json=transcript_json,
            ips_json=ips_json,
            transcript_title=transcript_title,
            ips_title=ips_title,
            transcript_output_path=transcript_output_path,
            ips_output_path=ips_output_path,
        )
    finally:
        upload_path.unlink(missing_ok=True)


def run_stt_pipeline(audio_file_path: str) -> tuple[list[dict], dict]:
    from app.stt.stt_record import (  # noqa: PLC0415
        extract_customer_text,
        extract_goal_rrttllu,
        map_speaker_roles,
        transcribe_with_diarization,
        validate_env,
    )

    validate_env()
    transcript = transcribe_with_diarization(audio_file_path)
    mapped_transcript = map_speaker_roles(transcript)
    customer_text = extract_customer_text(mapped_transcript)
    ips_json = extract_goal_rrttllu(customer_text)

    return mapped_transcript, ips_json


def _save_upload_file(audio_file: UploadFile, upload_path: Path) -> None:
    with upload_path.open("wb") as output:
        while chunk := audio_file.file.read(1024 * 1024):
            output.write(chunk)


def _save_json(data: list[dict] | dict, output_path: Path) -> None:
    from app.stt.stt_record import save_json  # noqa: PLC0415

    save_json(data, output_path)
