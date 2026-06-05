import json


INPUT_FILE = "transcript_result.json"
OUTPUT_FILE = "mapped_transcript_result.json"

# Guest-1, Guest-2 -> PB, 고객으로 매핑
SPEAKER_ROLE_MAP = {
    "Guest-1": "PB",
    "Guest-2": "고객"
}


def map_speaker_roles():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    mapped_result = []

    for item in transcript:
        speaker_label = item.get("speaker_label")
        speaker_role = SPEAKER_ROLE_MAP.get(speaker_label, "Unknown")

        mapped_item = {
            **item,
            "speaker_role": speaker_role
        }

        mapped_result.append(mapped_item)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapped_result, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {OUTPUT_FILE}")


if __name__ == "__main__":
    map_speaker_roles()