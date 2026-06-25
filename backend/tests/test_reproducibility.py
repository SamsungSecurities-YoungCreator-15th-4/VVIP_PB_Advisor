"""재현성(reproducibility) 회귀 테스트 — 우리 과제의 핵심 차별점 증명.

원칙
----
- "같은 입력 → 항상 같은 출력"을 증명한다. 구체 숫자를 박지 않는 결정성/불변식
  테스트가 1순위라 로직이 바뀌어도 잘 깨지지 않는다.
- 부동소수점도 정확 일치(==)를 기대한다. 재현성이 핵심이므로 approx 를 쓰지 않는다.
- 외부 의존(Azure 임베딩, Supabase 연결)은 monkeypatch 로 격리하거나 skip 한다.

대상 함수 (develop 기준 #27 절세 seed / #32 RAG 머지 후 실제 코드에서 조사)
- app.services.ips.flatten_ips_json / build_ips_snapshot_payload
- app.services.transcript.transcript_to_raw_note
- app.stt.stt_record.format_ticks_as_mmss / map_speaker_roles / extract_customer_text
- app.rag.generate.ExtractiveGenerator.generate
- app.rag.retrieval.search_chunks (RPC 결과 → citation 변환부; 임베딩 호출 제외)
- app.routers.consultations._build_stt_titles / _parse_datetime / _consultation_date / _to_kst_iso

주의: 절세 "세후/절세액 계산 함수"는 develop 현재 코드에 존재하지 않는다(seed.sql 은
규칙표일 뿐 Python 계산 로직이 없음). 해당 골든값 테스트는 함수 부재를 명시하며 skip 한다.
가짜 계산 로직을 만들지 않는다(AGENTS.md 금융 도메인 규칙).
"""

import ast
from pathlib import Path

import pytest

from app.rag.generate import (
    ExtractiveGenerator,
    fallback_insight_summary,
    normalize_insight_summary,
    strip_markdown,
)
from app.services.ips import (
    build_ips_snapshot_payload,
    fill_missing_ips_values,
    flatten_ips_json,
)
from app.services.transcript import transcript_to_raw_note
from app.stt.stt_record import (
    extract_customer_text,
    extract_goal_rrttllu,
    extract_ips_source_text,
    format_all_speech_as_ips_source,
    format_ticks_as_mmss,
    map_speaker_roles,
)

APP_DIR = Path(__file__).resolve().parents[1] / "app"


# ---------------------------------------------------------------------------
# 공통 픽스처 입력 (불변·해시 가능한 형태로 정의해 재사용)
# ---------------------------------------------------------------------------

RAW_IPS_NESTED = {
    "Goal": "노후 자산 안정적 운용",
    "Asset": "5000000000",
    "RRTTLLU": {
        "Return": "4.5",
        "Risk": "중립",
        "Time": 10,
        "Tax": "절세 중요",
        "Liquidity": "3년 락업 가능",
        "Legal": "상속 고려",
        "Unique": "ESG 선호",
    },
}

TRANSCRIPT = [
    {"speaker_label": "Guest-1", "text": "안녕하세요 고객님.", "offset_ticks": 0},
    {"speaker_label": "Guest-2", "text": "네 안녕하세요.", "offset_ticks": 35_000_000},
    {"speaker_label": "Guest-2", "text": "자산 운용 상담받고 싶어요.", "offset_ticks": 70_000_000},
    {"speaker_label": "Guest-1", "text": "어떤 목적이실까요?", "offset_ticks": 120_000_000},
]

CHUNKS = [
    {
        "title": "국세청 2026 세금가이드 1권",
        "chunk": "ISA 일반형 200만원 비과세.",
        "similarity": 0.91,
    },
    {"title": "삼성증권 저쿠폰 채권 전략", "chunk": "채권 자본차익은 비과세.", "similarity": 0.83},
]


# ===========================================================================
# 1순위 — 결정성 (값 하드코딩 없음)
# ===========================================================================


class TestIpsDeterminism:
    def test_flatten_ips_is_deterministic_over_n_calls(self):
        results = [flatten_ips_json(RAW_IPS_NESTED) for _ in range(5)]
        first = results[0]
        for r in results[1:]:
            assert r == first  # 5회 호출 모두 완전 동일

    def test_build_payload_is_deterministic(self):
        kwargs = dict(
            client_id="c-1",
            consultation_id="cons-1",
            source_type="consultation",
            raw_ips_json=flatten_ips_json(RAW_IPS_NESTED),
        )
        a = build_ips_snapshot_payload(**kwargs)
        b = build_ips_snapshot_payload(**kwargs)
        assert a == b

    def test_numeric_normalization_is_exact_float(self):
        # 부동소수점도 정확 일치를 기대한다(approx 금지).
        p1 = build_ips_snapshot_payload(
            client_id="c", consultation_id=None, source_type="initial",
            raw_ips_json=flatten_ips_json(RAW_IPS_NESTED),
        )
        p2 = build_ips_snapshot_payload(
            client_id="c", consultation_id=None, source_type="initial",
            raw_ips_json=flatten_ips_json(RAW_IPS_NESTED),
        )
        assert p1["return"] == p2["return"] == 4.5
        assert p1["asset"] == p2["asset"] == 5000000000.0

    def test_flatten_ips_invariant_all_keys_present(self):
        # 불변식: 출력은 IPS_KEYS 9개를 정확히 가진다(누락·추가 없음).
        from app.services.ips import IPS_KEYS

        flat = flatten_ips_json(RAW_IPS_NESTED)
        assert set(flat.keys()) == set(IPS_KEYS)

    def test_flat_input_passthrough_idempotent(self):
        # 이미 평탄화된 입력을 다시 평탄화해도 동일(멱등).
        flat = flatten_ips_json(RAW_IPS_NESTED)
        assert flatten_ips_json(flat) == flat

    def test_fill_missing_ips_values_uses_initial_only_for_missing_fields(self):
        extracted = {
            "Goal": "상담에서 새로 확인한 목표",
            "Asset": None,
            "Return": 0,
            "Risk": "",
            "Time": 3,
            "Tax": None,
            "Liquidity": "높음",
            "Legal": " ",
            "Unique": "해외 배당주 선호",
        }
        initial = flatten_ips_json(RAW_IPS_NESTED)

        merged = fill_missing_ips_values(extracted, initial)

        assert merged["Goal"] == "상담에서 새로 확인한 목표"
        assert merged["Asset"] == initial["Asset"]
        assert merged["Return"] == 0
        assert merged["Risk"] == initial["Risk"]
        assert merged["Time"] == 3
        assert merged["Tax"] == initial["Tax"]
        assert merged["Liquidity"] == "높음"
        assert merged["Legal"] == initial["Legal"]
        assert merged["Unique"] == "해외 배당주 선호"

    def test_fill_missing_ips_values_fills_omitted_keys_before_validation(self):
        extracted = {
            "Goal": "상담에서 새로 확인한 목표",
            "RRTTLLU": {
                "Risk": "공격형",
                "Unique": "해외 배당주 선호",
            },
        }
        initial = flatten_ips_json(RAW_IPS_NESTED)

        merged = fill_missing_ips_values(extracted, initial)

        assert merged["Goal"] == "상담에서 새로 확인한 목표"
        assert merged["Asset"] == initial["Asset"]
        assert merged["Return"] == initial["Return"]
        assert merged["Risk"] == "공격형"
        assert merged["Time"] == initial["Time"]
        assert merged["Tax"] == initial["Tax"]
        assert merged["Liquidity"] == initial["Liquidity"]
        assert merged["Legal"] == initial["Legal"]
        assert merged["Unique"] == "해외 배당주 선호"


class TestTranscriptDeterminism:
    def test_raw_note_is_deterministic(self):
        outs = [transcript_to_raw_note(TRANSCRIPT) for _ in range(3)]
        assert outs[0] == outs[1] == outs[2]

    def test_raw_note_line_count_invariant(self):
        # 불변식: 출력 줄 수 == 입력 발화 수.
        note = transcript_to_raw_note(TRANSCRIPT)
        assert len(note.splitlines()) == len(TRANSCRIPT)


class TestSttDeterminism:
    def test_format_ticks_is_deterministic(self):
        assert format_ticks_as_mmss(125_000_000) == format_ticks_as_mmss(125_000_000)

    def test_format_ticks_none_is_stable(self):
        assert format_ticks_as_mmss(None) == "00:00"

    def test_map_speaker_roles_is_deterministic(self):
        a = map_speaker_roles(TRANSCRIPT)
        b = map_speaker_roles(TRANSCRIPT)
        assert a == b

    def test_map_speaker_roles_merge_invariant(self):
        # 불변식: 연속된 동일 화자 발화는 하나로 병합된다.
        mapped = map_speaker_roles(TRANSCRIPT)
        for prev, cur in zip(mapped, mapped[1:]):
            assert prev["speaker_role"] != cur["speaker_role"]

    def test_extract_customer_text_is_deterministic(self):
        mapped = map_speaker_roles(TRANSCRIPT)
        assert extract_customer_text(mapped) == extract_customer_text(mapped)

    def test_extract_customer_text_only_customer(self):
        # 불변식: 고객 발화만 추출된다(PB 발화 제외).
        mapped = map_speaker_roles(TRANSCRIPT)
        out = extract_customer_text(mapped)
        assert "어떤 목적이실까요" not in out  # PB 발화
        assert "자산 운용 상담받고 싶어요" in out  # 고객 발화

    def test_extract_ips_source_text_falls_back_to_all_speech(self):
        single_speaker_transcript = [
            {
                "speaker_label": "Guest-1",
                "text": "자산 20억을 5년 정도 운용하고 싶습니다.",
                "offset_ticks": 0,
            }
        ]
        mapped = map_speaker_roles(single_speaker_transcript)

        assert extract_customer_text(mapped) == ""
        source_text, source_label = extract_ips_source_text(mapped)

        assert source_label == "전체 화자 발화"
        assert "PB: 자산 20억을 5년 정도 운용하고 싶습니다." in source_text

    def test_format_all_speech_skips_empty_text(self):
        source_text = format_all_speech_as_ips_source(
            [
                {"speaker_role": "PB", "text": None, "utterance_time": "00:00"},
                {"speaker_role": "고객", "text": "   ", "utterance_time": "00:01"},
                {"speaker_role": "고객", "text": " 목표 5% ", "utterance_time": "00:02"},
            ]
        )

        assert source_text == "[00:02] 고객: 목표 5%"

    def test_extract_goal_rrttllu_empty_source_uses_label(self):
        with pytest.raises(ValueError, match="전체 화자 발화가 비어 있어"):
            extract_goal_rrttllu("", source_label="전체 화자 발화")


class TestRagGeneratorDeterminism:
    def test_extractive_generate_is_deterministic(self):
        g = ExtractiveGenerator()
        a = g.generate("ISA 절세 효과는?", CHUNKS)
        b = g.generate("ISA 절세 효과는?", CHUNKS)
        assert a == b

    def test_extractive_generate_grounding_invariant(self):
        # "할루시네이션=즉사" 불변식: 모든 청크 원문이 answer 안에 그대로 들어간다
        # (검색된 근거 밖의 내용을 만들지 않는다).
        g = ExtractiveGenerator()
        answer = g.generate("질의", CHUNKS)
        for chunk in CHUNKS:
            assert chunk["chunk"].strip() in answer

    def test_extractive_generate_empty_chunks_raises(self):
        with pytest.raises(ValueError):
            ExtractiveGenerator().generate("질의", [])

    def test_insight_summary_fallback_is_deterministic_and_bounded(self):
        answer = (
            "절세와 유동성 니즈가 함께 확인됩니다. 제공된 자료 기준입니다."
        )
        a = fallback_insight_summary(answer)
        b = fallback_insight_summary(answer)
        assert a == b
        assert 0 < len(a) <= 90
        assert "제공된 자료" not in a
        assert not a.endswith(("습니다", "입니다", "됩니다"))

    def test_strip_markdown_removes_emphasis_headers_and_bullets(self):
        raw = (
            "## 미국 금리 동향\n"
            "- 미국 10년물 금리는 **4%** 아래로 하락했습니다.\n"
            "1. `국채` 금리 전망\n"
            "```python\nprint('hello')\n```"
        )
        out = strip_markdown(raw)
        for marker in ("**", "##", "`"):
            assert marker not in out
        # 내용(텍스트)은 보존된다(코드펜스 안쪽 코드 포함).
        assert "미국 금리 동향" in out
        assert "4%" in out
        assert "국채" in out
        assert "print('hello')" in out

    def test_fallback_skips_preamble_and_list_number(self):
        answer = (
            "현재 금리에 대한 주요 내용을 요약해 드리겠습니다. "
            "1. 한국 국채 10년물 금리는 2.9~3.2%로 예상됩니다."
        )
        summary = fallback_insight_summary(answer)
        # 도입 인사말·리스트 번호가 요약으로 새어 나오지 않는다.
        assert "드리겠습니다" not in summary
        assert not summary.lstrip().startswith("1")
        assert "금리" in summary
        assert 0 < len(summary) <= 90

    def test_fallback_prefers_numeric_evidence_sentence(self):
        answer = (
            "1. 시장 변동성 관리가 필요합니다. "
            "2. 한국 국채 10년물 금리는 2.9~3.2% 범위로 예상됩니다."
        )
        summary = fallback_insight_summary(answer)
        assert "2.9~3.2%" in summary
        assert "금리" in summary
        assert "금리는" not in summary
        assert 0 < len(summary) <= 90

    def test_normalize_insight_summary_removes_prefix_and_bounds_length(self):
        raw = "요약: " + "절세와 유동성 니즈를 함께 고려한 보수적 상담 포인트입니다" * 2
        summary = normalize_insight_summary(raw)
        assert not summary.startswith("요약:")
        assert len(summary) <= 90

    def test_normalize_insight_summary_preserves_numeric_summary(self):
        summary = normalize_insight_summary(
            "요약: 미국 10년물 금리 4.1% 상회와 변동성 확대에 따른 채권 듀레이션 관리 필요"
        )
        assert "4.1%" in summary
        assert "듀레이션 관리 필요" in summary
        assert len(summary) <= 90

    def test_normalize_insight_summary_keeps_short_financial_terms(self):
        assert "시가 50억원" in normalize_insight_summary("시가 50억원 기준")
        assert normalize_insight_summary("시가 상승") == "시가 상승"
        assert "높은 5%" in normalize_insight_summary("높은 5% 변동성")

    def test_normalize_insight_summary_converts_sentence_to_noun_phrase(self):
        assert normalize_insight_summary("금리가 상승했습니다.") == "금리 상승"
        assert (
            normalize_insight_summary("요약: 유동성 니즈가 확인됩니다.")
            == "유동성 니즈 확인"
        )
        assert normalize_insight_summary("상승세를 보입니다.") == "상승세 보임"
        assert normalize_insight_summary("금리 인하가 예상됩니다.") == "금리 인하 예상"
        assert normalize_insight_summary("시장 변동성이 높입니다.") == "시장 변동성 높임"
        assert normalize_insight_summary("세금 부담을 줄입니다.") == "세금 부담 줄임"


class TestRagSearchTransformDeterminism:
    """search_chunks 의 RPC→citation 변환부만 검증한다(임베딩·DB 연결은 격리).

    임베딩 호출은 외부 의존이라 비결정 → 테스트 대상에서 제외하고,
    RPC 가 같은 행을 돌려주면 변환 결과가 항상 같은지(결정성)만 본다.
    """

    @staticmethod
    def _fake_supabase():
        rpc_rows = [
            {"document_id": "d1", "content": "ISA 비과세 한도 200만원.", "similarity": 0.9},
            {"document_id": "d2", "content": "채권 자본차익 비과세.", "similarity": 0.8},
        ]
        docs = [
            {
                "id": "d1",
                "title": "세금가이드 1권",
                "source_type": "tax",
                "meta": {"published_date": "2026-01-01"},
            },
            {"id": "d2", "title": "채권 전략", "source_type": "house_view", "meta": {}},
        ]

        class _Result:
            def __init__(self, data):
                self.data = data

        class _TableQuery:
            def __init__(self, data):
                self._data = data

            def select(self, *a, **k):
                return self

            def in_(self, *a, **k):
                return self

            def execute(self):
                return _Result(self._data)

        class _RpcQuery:
            def __init__(self, data):
                self._data = data

            def execute(self):
                return _Result(self._data)

        class _Fake:
            def rpc(self, name, params):
                assert name == "match_document_chunks"
                return _RpcQuery(rpc_rows)

            def table(self, name):
                assert name == "document"
                return _TableQuery(docs)

        return _Fake()

    def test_search_chunks_transform_is_deterministic(self, monkeypatch):
        import app.rag.retrieval as retrieval

        fake = self._fake_supabase()
        monkeypatch.setattr(retrieval, "get_supabase_client", lambda: fake)

        embedding = [0.0] * retrieval.EMBEDDING_DIM
        a = retrieval.search_chunks(embedding)
        b = retrieval.search_chunks(embedding)
        assert a == b

    def test_search_chunks_falsy_published_date_normalized_to_none(self, monkeypatch):
        # 불변식: 빈 published_date 는 None 으로 정규화된다(d2 meta 에 값 없음).
        import app.rag.retrieval as retrieval

        monkeypatch.setattr(retrieval, "get_supabase_client", self._fake_supabase)
        result = retrieval.search_chunks([0.0] * retrieval.EMBEDDING_DIM)
        by_id = {c["doc_id"]: c for c in result}
        assert by_id["d2"]["published_date"] is None
        assert by_id["d1"]["published_date"] == "2026-01-01"


# ===========================================================================
# as_of(기준시점) 주입 — 같은 as_of → 같은 출력
# ===========================================================================


class TestAsOfInjection:
    def test_parse_datetime_is_deterministic(self):
        from app.routers.consultations import _parse_datetime

        a = _parse_datetime("2026-06-14T09:30:00Z")
        b = _parse_datetime("2026-06-14T09:30:00Z")
        assert a == b

    def test_consultation_date_and_iso_deterministic(self):
        from app.routers.consultations import _consultation_date, _to_kst_iso

        ts = "2026-06-14T23:30:00Z"  # UTC 23:30 → KST 다음날
        assert _consultation_date(ts) == _consultation_date(ts) == "2026-06-15"
        assert _to_kst_iso(ts) == _to_kst_iso(ts)

    def test_build_stt_titles_same_now_same_output(self):
        # as_of(now)를 주입하면 같은 now → 같은 타이틀(시간 의존성이 주입형이라 재현 가능).
        from datetime import datetime

        from app.routers.consultations import KST, _build_stt_titles

        class _Result:
            count = 0
            data = []

        class _Q:
            def select(self, *a, **k):
                return self

            def eq(self, *a):
                return self

            def gte(self, *a):
                return self

            def lt(self, *a):
                return self

            def execute(self):
                return _Result()

        class _SB:
            def table(self, *a):
                return _Q()

        now = datetime(2026, 6, 14, 10, 0, tzinfo=KST)
        a = _build_stt_titles(supabase=_SB(), client_id="c", customer_name="홍길동", now=now)
        b = _build_stt_titles(supabase=_SB(), client_id="c", customer_name="홍길동", now=now)
        assert a == b
        assert a == ("260614_홍길동_상담 스크립트(1)", "260614_홍길동_ips(1)")


# ===========================================================================
# 2순위 — 시드/시간 의존성 정적 검사 (계산 모듈에 한정)
# ===========================================================================

# 순수 계산/변환 모듈: 여기서는 비결정 호출(now/random/uuid/time)이 0 이어야 한다.
PURE_CALC_MODULES = [
    APP_DIR / "services" / "ips.py",
    APP_DIR / "services" / "transcript.py",
    APP_DIR / "rag" / "generate.py",
]

# (모듈 힌트, 메서드명): 메서드명이 체인의 끝이고 모듈 힌트가 체인 앞쪽 어디든
# 등장하면 탐지. datetime.now / datetime.datetime.now / date.today /
# datetime.date.today / time.time / uuid.uuid4 같은 중첩 형태를 모두 잡는다.
_FORBIDDEN_METHODS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("time", "perf_counter"),
    ("uuid", "uuid1"),
    ("uuid", "uuid4"),
}

# 체인 어디에든 이 세그먼트가 있으면 비결정으로 본다(random.* / np.random.* /
# numpy.random.* 전체를 한 번에 커버).
_FORBIDDEN_MODULE_SEGMENTS = {"random"}

# from uuid import uuid4 처럼 직접 import 해 호출하는 이름.
_FORBIDDEN_BARE_NAMES = {"uuid1", "uuid4"}


def _attr_chain(node: ast.Attribute) -> tuple[str, ...]:
    """a.b.c() 의 ast.Attribute 를 ('a','b','c') 튜플로 평탄화한다."""
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return tuple(reversed(parts))


def _nondeterministic_calls(source: str) -> list[str]:
    """AST 로 비결정 호출(now/today/random/uuid 등)을 찾아 'lineno:이름' 목록 반환.

    탐지 규칙(접두사 정확일치에 의존하지 않아 중첩/모듈형 우회를 막는다):
    - 메서드형: 체인 끝이 금지 메서드이고 모듈 힌트가 체인 앞쪽에 등장
      → datetime.datetime.now() 같은 doubled 형태도 탐지.
    - 모듈형: 체인 앞쪽에 random 세그먼트 존재 → random.* / np.random.* 모두 탐지.
    - 직접 import 형: uuid4/uuid1 단독 이름 호출.
    """
    tree = ast.parse(source)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain = _attr_chain(node)
            if not chain:
                continue
            label = f"{node.lineno}:{'.'.join(chain)}"
            method, prefix = chain[-1], chain[:-1]
            if any(hint in prefix and method == attr for hint, attr in _FORBIDDEN_METHODS):
                hits.append(label)
            elif any(seg in _FORBIDDEN_MODULE_SEGMENTS for seg in prefix):
                hits.append(label)
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_BARE_NAMES:
            hits.append(f"{node.lineno}:{node.id}")
    return hits


@pytest.mark.parametrize(
    "snippet",
    [
        "import random\nx = random.random()",  # random.* (len-1 규칙)
        "import numpy as np\nx = np.random.seed(1)",  # np.random.*
        "import uuid\nx = uuid.uuid4()",  # 모듈형 uuid
        "from uuid import uuid4\nx = uuid4()",  # 직접 import
        "import datetime\nx = datetime.datetime.now()",  # doubled 우회
        "import datetime\nx = datetime.date.today()",  # doubled date.today
        "import datetime\nx = datetime.now()",  # from datetime import datetime 형
        "import time\nx = time.time()",
    ],
)
def test_static_checker_detects_nondeterministic_forms(snippet):
    # 검사기 자체가 우회 형태(중첩/모듈형/직접 import)를 잡는지 회귀로 고정.
    assert _nondeterministic_calls(snippet), f"미탐지: {snippet!r}"


@pytest.mark.parametrize(
    "snippet",
    [
        "d = {}\nd['time'] = 1",  # dict 키 'time' — 메서드 호출 아님
        "obj.time\nobj.now",  # 모듈 힌트 없는 단순 속성 접근
        "from datetime import time\nx = time.min",  # time.min 은 비결정 아님
    ],
)
def test_static_checker_no_false_positive(snippet):
    assert _nondeterministic_calls(snippet) == [], f"오탐: {snippet!r}"


@pytest.mark.parametrize("module_path", PURE_CALC_MODULES, ids=lambda p: p.name)
def test_pure_calc_modules_have_no_nondeterministic_calls(module_path):
    source = module_path.read_text(encoding="utf-8")
    hits = _nondeterministic_calls(source)
    assert hits == [], (
        f"{module_path.name} 에 비결정 호출이 있습니다(재현성 위반): {hits}. "
        "now()/random/uuid 등은 입력으로 주입해야 합니다."
    )


# ===========================================================================
# 3순위 — 절세 골든값 회귀 (함수 부재로 보류)
# ===========================================================================


@pytest.mark.skip(
    reason="절세 세후/절세액 계산 함수가 develop 현재 코드에 없음. seed.sql 은 "
    "규칙표(tax_rule)일 뿐 Python 계산 로직 미구현. 계산 함수가 추가되면 "
    "seed 규칙(ISA 200만 비과세·9.9% 분리과세, 해외주식 22%·250만 공제, "
    "금융소득종합과세 2천만 임계 등)으로 골든값 회귀와 불변식"
    "(일반과세 세금 >= 절세 세금, 세전 = 세후 + 세금)을 추가한다."
)
def test_tax_after_tax_golden_values():  # pragma: no cover
    raise NotImplementedError
