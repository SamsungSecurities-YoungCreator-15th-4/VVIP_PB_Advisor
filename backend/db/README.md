# DB Schema — Supabase CLI로 이전됨

> ⚠️ DB 스키마·마이그레이션은 **`supabase/migrations/`** 로 이전되어 **Supabase CLI**로 관리합니다.
> 이 폴더(`backend/db/`)의 `schema.sql`·`migrations/`는 제거되었습니다. 더 이상 여기에 SQL을 추가하지 마세요.

## 현재 위치

| 항목 | 새 위치 |
| --- | --- |
| baseline (v0.1, 9개 테이블·RAG 함수·RLS) | `supabase/migrations/20260605000000_baseline_v0_1.sql` |
| 0001 (FK 인덱스 3건 + RAG 임계값) | `supabase/migrations/20260605000001_add_fk_indexes_and_threshold.sql` |
| CLI 설정 | `supabase/config.toml` |

## 새 마이그레이션 만들기

```bash
supabase migration new <이름>
# → supabase/migrations/<타임스탬프>_<이름>.sql 생성 후 SQL 작성
```

자세한 운영 절차(로그인·링크·동기화)는 **[`supabase/README.md`](../../supabase/README.md)** 참고.
