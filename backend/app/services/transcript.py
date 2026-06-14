def transcript_to_raw_note(transcript_json: list[dict]) -> str:
    lines = []
    for item in transcript_json:
        speaker_role = item.get("speaker_role", "Unknown")
        utterance_time = item.get("utterance_time", "00:00")
        text = item.get("text", "")
        lines.append(f"[{utterance_time}] {speaker_role}: {text}")

    return "\n".join(lines)
