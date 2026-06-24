"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { getSupabase } from "@/lib/supabaseClient";

function FloatInput({
  id,
  label,
  type = "text",
  value,
  onChange,
  rightSlot,
}: {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  rightSlot?: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  const lifted = focused || value.length > 0;

  return (
    <div className="relative">
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        className={`w-full rounded-lg border-2 px-4 pb-3 pt-7 text-[16px] font-medium text-gray-900 outline-none transition-colors ${
          focused ? "border-brand" : "border-gray-200"
        } ${rightSlot ? "pr-11" : ""}`}
      />
      <label
        htmlFor={id}
        className={`pointer-events-none absolute left-3 bg-white px-0.5 font-bold transition-all ${
          lifted
            ? `top-[-0.55rem] text-[11px] ${focused ? "text-brand" : "text-gray-400"}`
            : "top-[1.05rem] text-[14px] text-gray-400"
        }`}
      >
        {label}
      </label>
      {rightSlot && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {rightSlot}
        </div>
      )}
    </div>
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    // ID 입력란을 이메일로 사용한다(Supabase Auth 는 이메일+비밀번호).
    const { error: signInError } = await getSupabase().auth.signInWithPassword({
      email: id.trim(),
      password,
    });
    setSubmitting(false);
    if (signInError) {
      setError("아이디(이메일) 또는 비밀번호가 올바르지 않습니다.");
      return;
    }
    router.push("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white">
      <div className="w-full max-w-[460px] px-10">
        {/* 로고 */}
        <div className="mb-12 flex flex-col items-center gap-4">
          <img src="/logo.png" alt="S.upervisor" className="h-[72px] w-[72px] rounded-3xl object-cover shadow-sm" />
          <h1 className="text-[28px] font-extrabold text-brand">S.upervisor</h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <FloatInput id="pb-id" label="ID" value={id} onChange={setId} />

          <FloatInput
            id="pb-pw"
            label="Password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={setPassword}
            rightSlot={
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="text-gray-400 transition-colors hover:text-gray-600"
                tabIndex={-1}
                aria-label={showPassword ? "비밀번호 숨기기" : "비밀번호 보기"}
              >
                {showPassword ? (
                  <EyeOff className="size-5" />
                ) : (
                  <Eye className="size-5" />
                )}
              </button>
            }
          />

          {error && (
            <p className="text-[13px] font-medium text-red-600" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-3 w-full rounded-xl bg-brand py-4 text-[17px] font-bold text-white transition-opacity hover:opacity-90 active:opacity-80 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
