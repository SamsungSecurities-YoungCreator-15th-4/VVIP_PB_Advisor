/**
 * Supabase 브라우저 클라이언트 (인증 전용).
 *
 * 이 인스턴스는 로그인/세션·access_token 관리에만 쓴다. 데이터 조회·생성은
 * 기존대로 FastAPI 백엔드(lib/api)를 통해 한다.
 *
 * anon 키는 공개 전제 키라 NEXT_PUBLIC_ 노출 OK. service_role 키는 절대 프론트에 두지 않는다.
 *
 * 주의: lib/api/clients.ts 의 createClient(고객 생성 함수)와 이름이 겹치지 않도록
 *       여기서는 supabase-js 의 createClient 를 `supabase` 인스턴스로만 내보낸다.
 */
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // 빌드/런타임에서 환경변수 누락을 빨리 드러낸다(.env.local 참고).
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY 가 설정되지 않았습니다 (.env.local 참고)",
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
