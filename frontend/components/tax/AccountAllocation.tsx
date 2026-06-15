import { TAX_EFFECT } from "@/lib/mockData";

/** ② 절세 계좌 배치 활용도 — ISA / 연금저축+IRP / 일반계좌 진행바 */
export default function AccountAllocation() {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[12px] font-extrabold">
        <span className="flex size-4 items-center justify-center rounded-full bg-brand/10 text-[10px] text-brand-dark">
          2
        </span>
        절세 계좌 배치 활용도
      </p>
      <div className="flex flex-col gap-2.5">
        {TAX_EFFECT.accounts.map((acct) => {
          const pct =
            acct.used !== null && acct.limit
              ? (acct.used / acct.limit) * 100
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
