import { TAX_EFFECT } from "@/lib/mockData";
import type { AccountSlot } from "@/lib/types";

type DisplayAccount = {
  name: string;
  tag: string;
  used: number | null;
  limit: number | null;
  caption: string;
};

// 계좌 key → 표시 메타. caption은 잔여 한도에 따라 동적으로 생성한다.
const ACCOUNT_META: Record<
  AccountSlot["key"],
  { name: string; tag: string; caption: (used: number, limit: number) => string }
> = {
  isa: {
    name: "ISA",
    tag: "비과세·분리과세",
    caption: (used, limit) =>
      used >= limit
        ? "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세"
        : `잔여 한도 ${(limit - used).toLocaleString()}만 · 비과세 200만 + 초과분 9.9% 분리과세`,
  },
  pension: {
    name: "연금저축 + IRP",
    tag: "세액공제",
    caption: (used, limit) =>
      used >= limit
        ? "세액공제 한도 소진 · 공제율 16.5%"
        : `잔여 한도 ${(limit - used).toLocaleString()}만 · 공제율 16.5%`,
  },
  general: {
    name: "일반계좌",
    tag: "분리과세 ETF",
    caption: () => "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
  },
};

function toDisplay(slots: AccountSlot[]): DisplayAccount[] {
  return slots.map((s) => {
    const meta = ACCOUNT_META[s.key];
    return {
      name: meta.name,
      tag: meta.tag,
      used: s.usedManwon,
      limit: s.limitManwon,
      caption:
        s.usedManwon !== null && s.limitManwon !== null
          ? meta.caption(s.usedManwon, s.limitManwon)
          : meta.caption(0, 0),
    };
  });
}

/** ② 절세 계좌 배치 활용도 — ISA / 연금저축+IRP / 일반계좌 진행바.
 *  accounts(라이브 계산)가 오면 그걸 쓰고, 없으면 목데이터로 폴백한다. */
export default function AccountAllocation({
  accounts,
}: {
  accounts?: AccountSlot[];
}) {
  const list: DisplayAccount[] =
    accounts && accounts.length > 0 ? toDisplay(accounts) : TAX_EFFECT.accounts;

  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          2
        </span>
        절세 계좌 배치 활용도
      </p>
      <div className="flex flex-col gap-2.5">
        {list.map((acct) => {
          const pct =
            acct.used !== null && acct.limit
              ? Math.min((acct.used / acct.limit) * 100, 100)
              : 45; // 일반계좌(잔여 자산 배치)는 표시용 더미 진행률
          return (
            <div key={acct.name}>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[12px] font-extrabold">
                  {acct.name}
                  <span className="rounded-md bg-brand/10 px-1.5 py-0.5 text-[12px] font-bold text-brand-dark">
                    {acct.tag}
                  </span>
                </span>
                {acct.used != null ? (
                  <span className="text-[12px] font-extrabold tabular-nums">
                    {acct.used.toLocaleString()}{" "}
                    <span className="font-bold text-muted-foreground/60">
                      / {acct.limit?.toLocaleString()}만
                    </span>
                  </span>
                ) : (
                  <span className="text-[12px] font-bold text-muted-foreground">
                    잔여 자산 배치
                  </span>
                )}
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-md bg-muted">
                <div
                  className={`h-full rounded-md bg-linear-to-r ${
                    acct.name === "일반계좌"
                      ? "from-[#B8D4FF] to-[#7AABFF]"
                      : "from-[#5C9CFF] to-brand"
                  }`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="mt-1 text-[12px] font-semibold leading-snug text-muted-foreground">
                {acct.caption}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
