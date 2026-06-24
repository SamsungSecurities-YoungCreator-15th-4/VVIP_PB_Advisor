"use client";

/**
 * 최소 인증 가드. 보호된 페이지를 감싸 Supabase 인증 상태를 구독하고,
 * 세션이 없으면 /login 으로 보낸다. 세션 확인 전에는 보호 콘텐츠를 렌더하지 않는다.
 *
 * onAuthStateChange 는 구독 즉시 현재 세션으로 한 번 호출되므로 초기 확인을 겸하고,
 * 이후 다른 탭 로그아웃·토큰 만료 등 런타임 상태 변화도 함께 반영한다.
 * (의도적으로 단순하게 유지 — 미들웨어/SSR 세션까지는 다루지 않는다.)
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/lib/supabaseClient";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const {
      data: { subscription },
    } = getSupabase().auth.onAuthStateChange((_event, session) => {
      if (!session) {
        setReady(false);
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
    return () => {
      subscription.unsubscribe();
    };
  }, [router]);

  if (!ready) return null;
  return <>{children}</>;
}
