"use client";

/**
 * 최소 인증 가드. 보호된 페이지를 감싸 마운트 시 Supabase 세션을 확인하고,
 * 세션이 없으면 /login 으로 보낸다. 세션 확인 전에는 보호 콘텐츠를 렌더하지 않는다.
 *
 * (의도적으로 단순하게 유지 — 미들웨어/SSR 세션까지는 다루지 않는다.)
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!active) return;
      if (!session) {
        router.replace("/login");
      } else {
        setReady(true);
      }
    });
    return () => {
      active = false;
    };
  }, [router]);

  if (!ready) return null;
  return <>{children}</>;
}
