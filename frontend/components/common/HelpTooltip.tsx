"use client";

import { useEffect, useRef, useState } from "react";
import { useDashboardStore } from "@/lib/store";

/**
 * 도움말 모드가 ON일 때만 hover 시 툴팁을 표시하는 래퍼.
 * fixed 포지셔닝을 사용해 overflow:hidden 부모에 잘리지 않는다.
 * 항상 children을 렌더링해 helpMode 전환 시 자식 state가 초기화되지 않는다.
 */
export default function HelpTooltip({
  children,
  text,
  placement = "top",
  className = "",
}: {
  children: React.ReactNode;
  text: string;
  placement?: "top" | "bottom";
  className?: string;
}) {
  const helpMode = useDashboardStore((s) => s.helpMode);
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const handleMouseEnter = () => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    setPos({
      x: r.left + r.width / 2,
      y: placement === "bottom" ? r.bottom : r.top,
    });
  };

  const handleMouseLeave = () => setPos(null);

  useEffect(() => {
    if (!pos) return;
    const clear = () => setPos(null);
    window.addEventListener("scroll", clear, true);
    window.addEventListener("resize", clear);
    return () => {
      window.removeEventListener("scroll", clear, true);
      window.removeEventListener("resize", clear);
    };
  }, [pos]);

  return (
    <div
      ref={ref}
      className={`relative ${className}`}
      onMouseEnter={helpMode ? handleMouseEnter : undefined}
      onMouseLeave={helpMode ? handleMouseLeave : undefined}
    >
      {children}

      {helpMode && pos && (
        <span className="pointer-events-none absolute inset-0 rounded-lg bg-brand/[0.07]" />
      )}

      {helpMode && pos && (
        <div
          className="pointer-events-none fixed z-[9999] w-60 rounded-xl bg-foreground px-3 py-2.5 text-[13px] font-semibold leading-relaxed text-background shadow-xl"
          style={{
            left: pos.x,
            top: placement === "bottom" ? pos.y + 8 : pos.y - 8,
            transform:
              placement === "bottom"
                ? "translateX(-50%)"
                : "translateX(-50%) translateY(-100%)",
          }}
        >
          {text}
          <span
            className={`absolute left-1/2 -translate-x-1/2 border-4 border-transparent ${
              placement === "bottom"
                ? "bottom-full border-b-foreground"
                : "top-full border-t-foreground"
            }`}
          />
        </div>
      )}
    </div>
  );
}
