"""Azure AI Speech 실시간 전사 파이프라인.

stt_record.py 는 업로드된 음성 파일을 ConversationTranscriber 에 넘겨 일괄
전사한다. 이 모듈은 같은 Azure Speech 모델의 실시간 입력(PushAudioInputStream /
microphone)을 사용하되, 화자 분리 결과 후처리와 Goal/RRTTLLU 추출은 기존
stt_record.py 로직을 그대로 재사용한다.

실서비스에서는 Render 백엔드가 사용자 기기의 마이크를 직접 열 수 없다.
브라우저/앱이 내장 마이크 권한을 받아 PCM 오디오 청크를 WebSocket으로
전송하고, 백엔드는 그 스트림을 전사한다.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

STT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = STT_DIR.parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.stt.stt_record import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    GOAL_RRTTLLU_OUTPUT_FILE,
    MAPPED_TRANSCRIPT_OUTPUT_FILE,
    SPEECH_KEY,
    SPEECH_REGION,
    extract_customer_text,
    extract_goal_rrttllu,
    map_speaker_roles,
    save_json,
    validate_env,
)

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_BITS_PER_SAMPLE = 16
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_DELAY_SECONDS = 0.02


TranscriptCallback = Callable[[dict], None]


def _build_speech_config() -> speechsdk.SpeechConfig:
    speech_config = speechsdk.SpeechConfig(
        subscription=SPEECH_KEY,
        region=SPEECH_REGION,
    )
    speech_config.speech_recognition_language = "ko-KR"
    return speech_config


def _build_push_audio_stream(
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    bits_per_sample: int = DEFAULT_BITS_PER_SAMPLE,
    channels: int = DEFAULT_CHANNELS,
) -> speechsdk.audio.PushAudioInputStream:
    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=sample_rate,
        bits_per_sample=bits_per_sample,
        channels=channels,
    )
    return speechsdk.audio.PushAudioInputStream(stream_format=stream_format)


class RealtimeConversationTranscriber:
    """실시간 오디오 청크를 받아 Azure ConversationTranscriber 로 전사한다.

    입력 오디오는 기본적으로 16kHz / 16-bit / mono PCM 바이트 스트림을
    기대한다. FastAPI WebSocket 이나 브라우저 MediaRecorder 연동부에서는 이
    형식에 맞춰 변환한 바이트를 write() 로 전달하면 된다.
    """

    def __init__(
        self,
        *,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        bits_per_sample: int = DEFAULT_BITS_PER_SAMPLE,
        channels: int = DEFAULT_CHANNELS,
        on_transcript: TranscriptCallback | None = None,
    ) -> None:
        validate_env()
        self._push_stream = _build_push_audio_stream(
            sample_rate=sample_rate,
            bits_per_sample=bits_per_sample,
            channels=channels,
        )
        audio_config = speechsdk.audio.AudioConfig(stream=self._push_stream)
        self._transcriber = speechsdk.transcription.ConversationTranscriber(
            speech_config=_build_speech_config(),
            audio_config=audio_config,
        )
        self._on_transcript = on_transcript
        self._results: list[dict] = []
        self._done = False
        self._started = False
        self._cancellation_error: RuntimeError | None = None

        self._transcriber.transcribed.connect(self._transcribed_handler)
        self._transcriber.canceled.connect(self._canceled_handler)
        self._transcriber.session_stopped.connect(self._session_stopped_handler)

    @property
    def results(self) -> list[dict]:
        return list(self._results)

    def start(self) -> None:
        if self._started:
            return
        logger.info("1/5 실시간 STT + 화자 분리 시작")
        self._transcriber.start_transcribing_async().get()
        self._started = True

    def write(self, audio_chunk: bytes) -> None:
        if not self._started:
            raise RuntimeError(
                "실시간 전사 세션이 시작되지 않았습니다. "
                "start()를 먼저 호출하세요."
            )
        if self._cancellation_error:
            raise self._cancellation_error
        if self._done:
            raise RuntimeError(
                "이미 종료된 실시간 전사 세션에는 오디오를 쓸 수 없습니다."
            )
        if audio_chunk:
            self._push_stream.write(audio_chunk)

    def stop(self, *, timeout_seconds: float = 15.0) -> list[dict]:
        if not self._started:
            return self.results

        # 입력 스트림을 먼저 닫아 더 이상 들어올 오디오가 없음을 알린다.
        self._push_stream.close()
        started_at = time.monotonic()

        try:
            while not self._done:
                if time.monotonic() - started_at > timeout_seconds:
                    raise RuntimeError(
                        "실시간 STT 전사 종료가 제한 시간을 초과했습니다."
                    )
                time.sleep(0.1)
        finally:
            try:
                self._transcriber.stop_transcribing_async().get()
            except Exception as cleanup_error:
                logger.warning("Realtime STT session cleanup failed: %s", cleanup_error)

        if self._cancellation_error:
            raise self._cancellation_error

        logger.info("Realtime STT transcription completed with %s segments", len(self._results))
        return self.results

    def _transcribed_handler(self, evt) -> None:
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text
            if not text:
                return

            item = {
                "sequence": len(self._results) + 1,
                "speaker_label": evt.result.speaker_id,
                "speaker_role": None,
                "text": text,
                "offset_ticks": evt.result.offset,
                "duration_ticks": evt.result.duration,
            }
            self._results.append(item)
            if self._on_transcript:
                self._on_transcript(item)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            logger.info("Realtime STT segment had no recognized speech")

    def _canceled_handler(self, evt) -> None:
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
            detail_parts = [str(part) for part in [error_code, error_details] if part]
            detail_message = " / ".join(detail_parts) or "상세 오류 없음"
            self._cancellation_error = RuntimeError(
                f"실시간 STT 전사가 오류로 취소되었습니다: {detail_message}"
            )
            logger.warning("Realtime STT transcription canceled with error: %s", error_code)
        else:
            logger.info("Realtime STT transcription canceled: %s", reason)

        self._done = True

    def _session_stopped_handler(self, _evt) -> None:
        logger.info("Realtime STT transcription session stopped")
        self._done = True


def transcribe_realtime_chunks_with_diarization(
    audio_chunks: Iterable[bytes],
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    bits_per_sample: int = DEFAULT_BITS_PER_SAMPLE,
    channels: int = DEFAULT_CHANNELS,
    chunk_delay_seconds: float = 0.0,
    on_transcript: TranscriptCallback | None = None,
) -> list[dict]:
    """실시간으로 들어오는 PCM 오디오 청크 iterable 을 전사한다.

    실제 WebSocket 환경에서는 chunk_delay_seconds 를 0으로 두고, 수신되는 즉시
    write() 하는 형태로 쓰면 된다. 로컬 파일을 청크 단위로 흘려보내는
    테스트에서는 지연값을 줄 수 있다.
    """
    transcriber = RealtimeConversationTranscriber(
        sample_rate=sample_rate,
        bits_per_sample=bits_per_sample,
        channels=channels,
        on_transcript=on_transcript,
    )
    transcriber.start()
    for audio_chunk in audio_chunks:
        transcriber.write(audio_chunk)
        if chunk_delay_seconds > 0:
            time.sleep(chunk_delay_seconds)
    return transcriber.stop()


def transcribe_microphone_realtime_with_diarization(
    *,
    listen_seconds: float | None = None,
    on_transcript: TranscriptCallback | None = None,
) -> list[dict]:
    """로컬 개발용 마이크 실시간 전사.

    Render 같은 서버 환경에서는 마이크 장치가 없으므로 PushAudioInputStream
    기반 RealtimeConversationTranscriber 를 사용해야 한다.
    """
    validate_env()
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=_build_speech_config(),
        audio_config=audio_config,
    )
    results: list[dict] = []
    done = False
    cancellation_error: RuntimeError | None = None

    def transcribed_handler(evt) -> None:
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text
            if not text:
                return
            item = {
                "sequence": len(results) + 1,
                "speaker_label": evt.result.speaker_id,
                "speaker_role": None,
                "text": text,
                "offset_ticks": evt.result.offset,
                "duration_ticks": evt.result.duration,
            }
            results.append(item)
            if on_transcript:
                on_transcript(item)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            logger.info("Realtime microphone segment had no recognized speech")

    def canceled_handler(evt) -> None:
        nonlocal done, cancellation_error
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
            detail_parts = [str(part) for part in [error_code, error_details] if part]
            detail_message = " / ".join(detail_parts) or "상세 오류 없음"
            cancellation_error = RuntimeError(
                "마이크 실시간 STT 전사가 오류로 취소되었습니다: "
                f"{detail_message}"
            )
        done = True

    def session_stopped_handler(_evt) -> None:
        nonlocal done
        done = True

    transcriber.transcribed.connect(transcribed_handler)
    transcriber.canceled.connect(canceled_handler)
    transcriber.session_stopped.connect(session_stopped_handler)

    logger.info("1/5 마이크 실시간 STT + 화자 분리 시작")
    transcriber.start_transcribing_async().get()
    started_at = time.monotonic()
    try:
        while not done:
            if listen_seconds is not None and time.monotonic() - started_at >= listen_seconds:
                break
            time.sleep(0.1)
    finally:
        try:
            transcriber.stop_transcribing_async().get()
        except Exception as cleanup_error:
            logger.warning("Realtime microphone cleanup failed: %s", cleanup_error)

    if cancellation_error:
        raise cancellation_error
    logger.info("Realtime microphone transcription completed with %s segments", len(results))
    return results


def build_realtime_pipeline_result(
    transcript: list[dict],
    *,
    fallback_to_all_speech: bool = False,
) -> tuple[list[dict], dict]:
    """실시간 전사 결과에 기존 STT 후처리 파이프라인을 적용한다."""
    mapped_transcript = map_speaker_roles(transcript)
    customer_text = extract_customer_text(mapped_transcript)
    if fallback_to_all_speech and not customer_text.strip():
        customer_text = _format_all_speech_as_customer_text(mapped_transcript)
    goal_rrttllu = extract_goal_rrttllu(customer_text)
    return mapped_transcript, goal_rrttllu


def _format_all_speech_as_customer_text(mapped_transcript: list[dict]) -> str:
    """로컬 단일 마이크 테스트에서 전체 발화를 고객 입력으로 간주한다."""
    return "\n".join(
        f"[{item.get('utterance_time', '00:00')}] {item['text']}"
        for item in mapped_transcript
        if item.get("text")
    )


def run_realtime_chunks_pipeline(
    audio_chunks: Iterable[bytes],
    output_dir: str | Path,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    bits_per_sample: int = DEFAULT_BITS_PER_SAMPLE,
    channels: int = DEFAULT_CHANNELS,
    chunk_delay_seconds: float = 0.0,
    on_transcript: TranscriptCallback | None = None,
) -> tuple[list[dict], dict]:
    """실시간 오디오 청크 전사부터 JSON 저장까지 실행한다."""
    transcript = transcribe_realtime_chunks_with_diarization(
        audio_chunks,
        sample_rate=sample_rate,
        bits_per_sample=bits_per_sample,
        channels=channels,
        chunk_delay_seconds=chunk_delay_seconds,
        on_transcript=on_transcript,
    )
    mapped_transcript, goal_rrttllu = build_realtime_pipeline_result(transcript)

    output_path = Path(output_dir)
    save_json(mapped_transcript, output_path / MAPPED_TRANSCRIPT_OUTPUT_FILE)
    save_json(goal_rrttllu, output_path / GOAL_RRTTLLU_OUTPUT_FILE)
    logger.info("5/5 실시간 STT 통합 파이프라인 완료")
    return mapped_transcript, goal_rrttllu


def _iter_pcm_file_chunks(file_path: str | Path, chunk_size: int) -> Iterable[bytes]:
    with Path(file_path).open("rb") as audio_file:
        while True:
            chunk = audio_file.read(chunk_size)
            if not chunk:
                break
            yield chunk


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "실시간 오디오 청크 전사, 화자 분리, 화자 매핑, "
            "고객 발화 추출, Goal/RRTTLLU JSON 구조화를 실행합니다. "
            "입력 옵션이 없으면 로컬 기본 마이크를 사용합니다."
        )
    )
    parser.add_argument(
        "--pcm-file",
        help=(
            "16kHz/16-bit/mono PCM raw 파일을 실시간 청크처럼 흘려보내 "
            "테스트합니다. 일반 WAV/MP3 파일은 stt_record.py를 사용하세요."
        ),
    )
    parser.add_argument(
        "--microphone",
        action="store_true",
        help=(
            "로컬 기본 마이크로 실시간 전사를 테스트합니다. "
            "입력 옵션이 없으면 기본값입니다."
        ),
    )
    parser.add_argument(
        "--listen-seconds",
        type=float,
        default=30.0,
        help="--microphone 사용 시 청취 시간. 기본값: 30초",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=3200,
        help="--pcm-file 사용 시 한 번에 보낼 바이트 수. 기본값: 3200",
    )
    parser.add_argument(
        "--chunk-delay-seconds",
        type=float,
        default=DEFAULT_CHUNK_DELAY_SECONDS,
        help="--pcm-file 사용 시 청크 사이 지연 시간. 기본값: 0.02초",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"결과 JSON을 저장할 폴더 경로. 기본값: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = parse_args()
    if args.microphone or not args.pcm_file:
        mic_transcript = transcribe_microphone_realtime_with_diarization(
            listen_seconds=args.listen_seconds
        )
        mapped, rrttllu = build_realtime_pipeline_result(
            mic_transcript,
            fallback_to_all_speech=True,
        )
        output = Path(args.output_dir)
        save_json(mapped, output / MAPPED_TRANSCRIPT_OUTPUT_FILE)
        save_json(rrttllu, output / GOAL_RRTTLLU_OUTPUT_FILE)
    elif args.pcm_file:
        run_realtime_chunks_pipeline(
            _iter_pcm_file_chunks(args.pcm_file, args.chunk_size),
            args.output_dir,
            chunk_delay_seconds=args.chunk_delay_seconds,
        )
