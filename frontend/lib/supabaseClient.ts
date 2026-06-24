/**
 * Supabase 브라우저 클라이언트 (인증 전용).
 *
 * 이 인스턴스는 로그인/세션·access_token 관리에만 쓴다. 데이터 조회·생성은
 * 기존대로 FastAPI 백엔드(lib/api)를 통해 한다.
 *
 * anon 키는 공개 전제 키라 NEXT_PUBLIC_ 노출 OK. service_role 키는 절대 프론트에 두지 않는다.
 *
 * 지연 생성(lazy): 모듈 로드 시점이 아니라 첫 사용 시점에 클라이언트를 만든다.
 *   - 빌드/정적 프리렌더(예: /login) 단계에서는 env 가 없어도 import 만으로 터지지 않는다.
 *   - 실제 호출(getSession·signIn) 시점에 env 가 없으면 그때 명확히 에러를 낸다.
 *
 * 주의: lib/api/clients.ts 의 createClient(고객 생성 함수)와 이름이 겹치지 않도록
 *       여기서는 supabase-js 의 createClient 를 getSupabase() 안에서만 쓴다.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (client) return client;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 설정되지 않았습니다 (.env.local 참고)",
    );
  }

  client = createClient(supabaseUrl, supabaseAnonKey);
  return client;
}
