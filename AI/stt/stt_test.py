import os
import time
import json
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk


load_dotenv()

SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

AUDIO_FILE = "audio/consultation_sample.wav"


def transcribe_with_diarization(audio_file_path: str):
    if not SPEECH_KEY or not SPEECH_REGION:
        raise ValueError("AZURE_SPEECH_KEY 또는 AZURE_SPEECH_REGION이 .env에 설정되지 않았습니다.")

    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"음성 파일을 찾을 수 없습니다: {audio_file_path}")

    speech_config = speechsdk.SpeechConfig(
        subscription=SPEECH_KEY,
        region=SPEECH_REGION
    )

    # 한국어 STT
    speech_config.speech_recognition_language = "ko-KR"

    audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)

    # 화자 분리를 포함한 대화 전사
    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config,
        audio_config=audio_config
    )

    results = []
    done = False

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
                    "duration_ticks": evt.result.duration
                }

                results.append(item)
                print(f"{speaker_id}: {text}")

        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("인식된 음성이 없습니다.")

    def canceled_handler(evt):
        nonlocal done
        print(f"취소됨: {evt}")
        done = True

    def session_stopped_handler(evt):
        nonlocal done
        print("세션 종료")
        done = True

    transcriber.transcribed.connect(transcribed_handler)
    transcriber.canceled.connect(canceled_handler)
    transcriber.session_stopped.connect(session_stopped_handler)

    print("STT + 화자 분리 시작...")
    transcriber.start_transcribing_async()

    while not done:
        time.sleep(0.5)

    transcriber.stop_transcribing_async()

    return results


if __name__ == "__main__":
    transcript = transcribe_with_diarization(AUDIO_FILE)

    output_path = "transcript_result.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {output_path}")