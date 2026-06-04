import json


INPUT_FILE = "mapped_transcript_result.json"
OUTPUT_FILE = "customer_text.txt"


def extract_customer_text():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        transcript = json.load(f)

    customer_texts = [
        item["text"]
        for item in transcript
        if item.get("speaker_role") == "고객"
    ]

    customer_script = "\n".join(customer_texts)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(customer_script)

    print("고객 발화 추출 완료")
    print(customer_script)


if __name__ == "__main__":
    extract_customer_text()