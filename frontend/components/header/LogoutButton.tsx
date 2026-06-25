"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSupabase } from "@/lib/supabaseClient";

/**
 * 로그아웃 버튼(아이콘 전용·원형).
 *
 * 로그인이 Supabase Auth(signInWithPassword)로 이뤄지므로, 로그아웃도 같은
 * 세션을 종료(signOut)하는 것으로 충분하다. signOut 은 서버의 refresh token 을
 * 폐기하고 세션 쿠키를 삭제하며, 그 변화는 AuthGuard 의 onAuthStateChange 가
 * 감지해 /login 으로 보낸다. 다만 네트워크 오류 등으로 signOut 이 실패해도
 * 로컬 세션은 비워지므로, 화면 전환은 성공 여부와 무관하게(finally) 수행한다.
 *
 * 실수 클릭 방지를 위해 헤더 맨 우측에 두고, 흰 배경·연한 회색(가이드 토글과 동일) 아이콘으로
 * 비중요 액션임을 드러낸다. 글자는 빼고 호버 툴팁으로 의미를 안내한다.
 */
export default function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      // Supabase signOut은 예외 대신 { error }를 반환할 수 있다 — 디버깅용으로 기록.
      const { error } = await getSupabase().auth.signOut();
      if (error) console.error("로그아웃 중 오류:", error);
    } catch (err) {
      console.error("예기치 못한 로그아웃 오류:", err);
    } finally {
      // 성공·실패와 무관하게 로그인 화면으로 이동(로컬 세션은 이미 비워짐).
      router.replace("/login");
    }
  }

  return (
    <div className="group relative shrink-0">
      <Button
        variant="outline"
        size="icon"
        onClick={handleLogout}
        disabled={loading}
        aria-label="로그아웃"
        className="rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        <LogOut className="size-4" />
      </Button>
      {/* 호버 툴팁 — 글자를 뺀 대신 의미를 안내. 맨 우측이라 오른쪽 정렬로 화면 밖 잘림 방지. */}
      <div className="pointer-events-none absolute -bottom-9 right-0 z-50 hidden whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1.5 text-[11px] font-semibold text-background shadow-lg group-hover:block">
        로그아웃
        <span className="absolute -top-1 right-3 border-4 border-transparent border-b-foreground" />
      </div>
    </div>
  );
}
