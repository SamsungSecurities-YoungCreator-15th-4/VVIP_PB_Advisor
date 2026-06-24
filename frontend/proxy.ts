/**
 * Proxy (Next.js 16 — 구 middleware).
 *
 * 서버에서 모든 요청 전에 실행돼, 로그인 세션이 없으면 보호 경로 접근을 /login 으로
 * 막는다. 세션은 @supabase/ssr 가 '쿠키'에 저장하므로 여기(서버)에서 읽을 수 있다.
 *
 * 역할 분담:
 *   - proxy(여기): 라우트 진입 차단(서버 강제) + 만료 토큰 자동 갱신(쿠키 재기록)
 *   - 백엔드 API: 토큰 없으면 401 (실제 데이터 보호의 1차 방어선)
 *   - AuthGuard(클라이언트): 런타임 세션 변화(다른 탭 로그아웃 등) 반영
 * Next 문서 권고대로 proxy 는 'optimistic check' 이며 단독 인증수단이 아니다.
 *
 * 참고: @supabase/ssr Next.js 서버 클라이언트 패턴(createServerClient + cookies)
 *       frontend/node_modules/next/dist/docs/01-app/.../proxy.md
 */
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// 인증 없이 접근 가능한 공개 경로(로그인 화면). 무한 리다이렉트 방지에도 쓴다.
const PUBLIC_PATHS = ["/login"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
}

// getUser() 가 토큰을 갱신/삭제하면 그 세션 쿠키가 `from` 응답에 실린다. 리다이렉트
// 시 이를 옮겨 담지 않으면(특히 만료로 쿠키가 삭제된 경우) 브라우저에 무효 쿠키가
// 남아 매 요청마다 실패한 재검증이 반복된다. 그래서 모든 리다이렉트에서 쿠키를 보존한다.
function redirectTo(
  request: NextRequest,
  pathname: string,
  from?: NextResponse,
): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = pathname;
  url.search = "";
  const redirect = NextResponse.redirect(url);
  from?.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
  return redirect;
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  // env 누락 시 보호를 우회시키지 않는다(fail-closed). 단 /login 은 통과시켜
  // 무한 리다이렉트를 막는다.
  if (!supabaseUrl || !supabaseAnonKey) {
    return isPublic(pathname)
      ? NextResponse.next({ request })
      : redirectTo(request, "/login");
  }

  // Supabase 가 토큰을 갱신하면 이 response 의 쿠키에 새 세션을 다시 심는다.
  let response = NextResponse.next({ request });

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value),
        );
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // getUser() 는 쿠키의 토큰을 인증서버로 검증하고, 필요 시 갱신해 위 setAll 로
  // 새 쿠키를 심는다. (getSession 은 검증 없이 읽기만 하므로 서버에서는 getUser 사용)
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // 미인증 + 보호 경로 → 로그인으로(만료로 삭제된 세션 쿠키도 함께 정리).
  if (!user && !isPublic(pathname)) {
    return redirectTo(request, "/login", response);
  }

  // 인증됨 + 로그인 화면 → 홈으로(갱신된 세션 쿠키 보존).
  if (user && isPublic(pathname)) {
    return redirectTo(request, "/", response);
  }

  return response;
}

export const config = {
  // api(현재 라우트 없음), 정적 파일/이미지/파비콘, 정적 자원 확장자는 제외.
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
