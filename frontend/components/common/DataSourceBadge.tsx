import { AlertTriangle, Inbox, Wifi } from "lucide-react";
import type { DataSource } from "@/lib/api";

/**
 * 데이터 출처 배지 — 화면 값이 실데이터인지 데모(폴백)인지 명시한다.
 * 우리 거버넌스: 폴백 값을 실데이터인 척 보여주지 않는다.
 *  - live    : 실데이터(보통 배지 생략)
 *  - empty   : 정상 빈결과(데이터 없음)
 *  - fallback: 호출 실패 → 데모 데이터 표시 중 ⚠️
 */
export default function DataSourceBadge({
  source,
  note,
  className = "",
}: {
  source: DataSource;
  note?: string;
  className?: string;
}) {
  if (source === "live") return null;

  const config =
    source === "fallback"
      ? {
          Icon: AlertTriangle,
          label: "데모 데이터",
          // 눈에 거슬리지 않게 차분한 회색 톤. 단, 실데이터인 척 숨기진 않는다(거버넌스).
          cls: "border-muted-foreground/15 bg-muted/30 text-muted-foreground/60",
        }
      : {
          Icon: Inbox,
          label: "데이터 없음",
          cls: "border-muted-foreground/15 bg-muted/30 text-muted-foreground/60",
        };
  const { Icon, label, cls } = config;

  return (
    <span
      title={note}
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold ${cls} ${className}`}
    >
      <Icon className="size-2.5" />
      {label}
    </span>
  );
}

/** 실데이터 표시용 작은 라벨(원하면 사용). */
export function LiveBadge({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 ${className}`}
    >
      <Wifi className="size-3" />
      실데이터
    </span>
  );
}
