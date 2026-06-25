"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSupabase } from "@/lib/supabaseClient";

/**
 * 로그아웃 버튼.
 *
 * 로그인이 Supabase Auth(signInWithPassword)로 이뤄지므로, 로그아웃도 같은
 * 세션을 종료(signOut)하는 것으로 충분하다. 세션 쿠키가 사라지면 AuthGuard 의
 * onAuthStateChange 가 이를 감지해 /login 으로 보내지만, 즉각적인 화면 전환을
 * 위해 여기서도 직접 라우팅한다.
 */
export default function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      await getSupabase().auth.signOut();
      router.replace("/login");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      variant="outline"
      onClick={handleLogout}
      disabled={loading}
      className="shrink-0 border-brand font-bold text-brand hover:bg-brand/5 hover:text-brand"
    >
      <LogOut className="size-4" />
      <span className="hidden sm:inline">로그아웃</span>
    </Button>
  );
}
