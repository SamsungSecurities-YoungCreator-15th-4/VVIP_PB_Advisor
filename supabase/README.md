# Supabase (CLI 관리)

VVIP_PB_Advisor의 DB 스키마·마이그레이션을 **Supabase CLI** 표준 구조로 관리한다.

```
supabase/
  config.toml          # CLI 설정 (project_id = mmyhfklauorhnyppkqbq) — 커밋
  migrations/          # 마이그레이션 (타임스탬프 순서로 적용) — 커밋
    20260605000000_baseline_v0_1.sql                 # 기존 backend/db/schema.sql (v0.1)
    20260605000001_add_fk_indexes_and_threshold.sql  # 기존 0001 (Gemini high 반영 최종본)
  .gitignore           # CLI 로컬 전용 파일(.branches/.temp/.env*) 무시 — 커밋
```

> `config.toml`의 `project_id`는 엄밀히는 로컬 컨테이너 식별자다. 실제 클라우드 연결은 아래 `supabase link --project-ref`로 이뤄진다(연결 정보는 gitignore된 `supabase/.temp`에 저장).

## CLI 설치 (WSL / Ubuntu, sudo 불필요)

```bash
# 최신 리눅스 바이너리를 ~/.local/bin 에 설치 (PATH에 이미 포함)
curl -sSL -o /tmp/supabase.tar.gz \
  https://github.com/supabase/cli/releases/latest/download/supabase_linux_amd64.tar.gz
tar -xzf /tmp/supabase.tar.gz -C /tmp
mkdir -p ~/.local/bin
install -m 0755 /tmp/supabase ~/.local/bin/supabase
supabase --version   # 확인
```

---

## ⚠️ 동기화 절차 (WSL 터미널에서 직접 실행)

**전제: 이 마이그레이션들의 SQL은 이미 Supabase 웹 SQL Editor에서 수동 실행되어 DB에 반영된 상태다.**
그런데 CLI는 마이그레이션 적용 이력을 원격 DB의 `supabase_migrations.schema_migrations` 테이블로 추적하는데, 수동 실행분은 이 테이블에 기록돼 있지 않다. 그래서 그냥 `supabase db push`를 하면 CLI가 "아무것도 적용 안 됨"으로 보고 **이미 있는 마이그레이션을 다시 실행**하려 한다.

→ 정석은 `db push`(재실행)가 아니라, **이미 적용된 마이그레이션을 `migration repair`로 "applied" 표시**(SQL 재실행 없이 이력만 기록)하는 것이다.

> 우리 SQL은 `create ... if not exists` / `create or replace`라 재실행도 대체로 안전하지만, 이력 정합성을 위해 아래 정석 절차를 따른다.

### 0) 로그인 & 링크

```bash
supabase login                                      # access token 입력
supabase link --project-ref mmyhfklauorhnyppkqbq    # 원격 DB 비밀번호 입력
```

### 1) 현재 이력 상태 확인

```bash
supabase migration list --linked
```

`LOCAL`에는 두 마이그레이션이, `REMOTE`에는 (수동 실행분이 추적되지 않았으므로) 비어 있을 가능성이 높다.

### 2) 실제 DB에 0001이 반영됐는지 확인

baseline(v0.1)은 이미 실행된 것이 확정이다. **0001(FK 인덱스·임계값 함수)이 SQL Editor에서 이미 실행됐는지**만 확인하면 시나리오가 갈린다. SQL Editor에서 아래로 확인:

```sql
-- 인덱스 존재 여부
select indexname from pg_indexes
where indexname in (
  'idx_consultation_client_id',
  'idx_portfolio_option_consultation_id',
  'idx_proposal_portfolio_option_id'
);
-- match_document_chunks 에 similarity_threshold 인자 존재 여부
select pg_get_function_arguments(oid)
from pg_proc where proname = 'match_document_chunks';
```

### 3) 시나리오별 동기화

**시나리오 A — baseline·0001 모두 이미 DB에 반영됨** (2)에서 인덱스 3건·인자 3개 모두 확인)
두 마이그레이션 모두 SQL 재실행 없이 "applied"로만 기록:

```bash
supabase migration repair --status applied 20260605000000
supabase migration repair --status applied 20260605000001
supabase migration list --linked   # 둘 다 REMOTE에 찍혔는지 확인
```

**시나리오 B — baseline만 반영, 0001은 아직 미실행** (2)에서 인덱스/인자가 없음)
baseline만 applied로 기록한 뒤, 0001만 push로 실제 적용:

```bash
supabase migration repair --status applied 20260605000000
supabase db push                   # 미적용분(0001)만 실행
supabase migration list --linked   # 둘 다 REMOTE에 찍혔는지 확인
```

> 이후 새 마이그레이션은 `supabase migration new <이름>` 으로 만들고, 정상적으로 `supabase db push`로 배포하면 된다.
