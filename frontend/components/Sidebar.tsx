"use client";

import { RotateCcw, Sparkles, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import {
  CONSULT_DURATION,
  CONSULT_LOG,
  CUSTOMERS,
  IPS_DEFAULT,
} from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";

/** 좌측 사이드바: 고객 선택 · 상담 입력 · 상담 내역 · IPS 조율기 · 분석하기 */
export default function Sidebar() {
  const { selectedCustomerId, ips, setIps } = useDashboardStore();
  const customer =
    CUSTOMERS.find((c) => c.id === selectedCustomerId) ?? CUSTOMERS[0];

  return (
    <aside className="flex w-[300px] shrink-0 flex-col gap-2.5">
      {/* 고객 선택 */}
      <Card className="gap-0 p-3">
        <p className="mb-2 text-[10px] font-bold tracking-wider text-muted-foreground">
          고객 선택
        </p>
        <div className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#DCE9FF] to-[#B8D4FF] text-lg font-extrabold text-brand-dark">
            {customer.name[0]}
          </div>
          <div>
            <div className="flex items-center gap-2 text-[15px] font-extrabold">
              {customer.name}
              <span className="rounded-md bg-brand px-1.5 py-0.5 text-[9px] font-extrabold text-white">
                {customer.grade}
              </span>
            </div>
            <div className="mt-0.5 text-[11px] font-semibold text-muted-foreground">
              {customer.pbCode} · {customer.aumLabel}
            </div>
          </div>
        </div>
      </Card>

      {/* 상담 입력 — 실시간 전사 UI는 중간발표 단계에서 숨김 */}
      <Card className="gap-0 p-3">
        <p className="mb-2 text-[10px] font-bold tracking-wider text-muted-foreground">
          상담 입력
        </p>
        <button
          type="button"
          className="w-full rounded-xl border-[1.5px] border-dashed border-[#B8D4FF] bg-brand/5 p-3 text-center"
        >
          <span className="mx-auto mb-1.5 flex size-8 items-center justify-center rounded-full border border-[#DCE9FF] bg-white">
            <Upload className="size-4 text-brand" />
          </span>
          <span className="block text-[13px] font-bold text-brand-dark">
            음성 업로드
          </span>
          <span className="mt-0.5 block text-[10px] font-semibold text-muted-foreground">
            mp3, wav, m4a 지원
          </span>
        </button>
      </Card>

      {/* 상담 내역 */}
      <Card className="gap-0 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[13px] font-bold">상담 내역</p>
          <p className="text-[10px] font-bold text-muted-foreground">
            상담 시간 {CONSULT_DURATION}
          </p>
        </div>
        <div className="flex flex-col gap-1.5">
          {CONSULT_LOG.map((m, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span
                className={`mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[8.5px] font-extrabold text-white ${
                  m.speaker === "PB" ? "bg-brand" : "bg-[#ADB5BD]"
                }`}
              >
                {m.speaker}
              </span>
              <span className="flex-1 text-[11px] font-medium leading-snug text-muted-foreground">
                {m.text}
              </span>
              <span className="mt-0.5 shrink-0 text-[9px] font-semibold tabular-nums text-muted-foreground/60">
                {m.time}
              </span>
            </div>
          ))}
        </div>
        <Button variant="outline" size="sm" className="mt-2 w-full font-bold">
          <RotateCcw />
          지난 기록 대화 불러오기
        </Button>
      </Card>

      {/* IPS 조율기 */}
      <Card className="flex-1 gap-0 p-3">
        <div className="mb-1">
          <p className="text-[13px] font-bold">IPS 조율기</p>
          <p className="text-[10px] font-bold tracking-wider text-muted-foreground">
            GOAL · ASSET · R-R-T-T-L-L-U
          </p>
        </div>
        <IpsRow k="Goal" sub="목표">
          <span className="text-[11px] font-semibold text-muted-foreground">
            {IPS_DEFAULT.goal}
          </span>
        </IpsRow>
        <IpsRow k="Asset" sub="자산">
          <span className="text-xs font-extrabold tabular-nums text-brand-dark">
            {IPS_DEFAULT.assetLabel}
          </span>
        </IpsRow>
        <IpsRow k="Return" sub="수익">
          <div className="flex flex-1 items-center gap-2">
            <span className="w-8 text-xs font-extrabold tabular-nums text-brand-dark">
              {ips.returnPct}%
            </span>
            <Slider
              value={[ips.returnPct]}
              onValueChange={([v]) => setIps({ returnPct: v })}
              min={0}
              max={20}
              step={1}
              className="flex-1"
            />
          </div>
        </IpsRow>
        <IpsRow k="Risk" sub="위험">
          <Segment
            options={["안정형", "균형형", "공격형"] as const}
            value={ips.risk}
            onChange={(v) => setIps({ risk: v })}
          />
        </IpsRow>
        <IpsRow k="Time" sub="기간">
          <div className="flex flex-1 items-center gap-2">
            <span className="w-8 text-xs font-extrabold tabular-nums text-brand-dark">
              {ips.timeYears}년
            </span>
            <Slider
              value={[ips.timeYears]}
              onValueChange={([v]) => setIps({ timeYears: v })}
              min={1}
              max={30}
              step={1}
              className="flex-1"
            />
          </div>
        </IpsRow>
        <IpsRow k="Tax" sub="세제">
          <span className="text-[11px] font-semibold text-muted-foreground">
            {IPS_DEFAULT.tax}
          </span>
        </IpsRow>
        <IpsRow k="Liquid" sub="유동성">
          <Segment
            options={["낮음", "중간", "높음"] as const}
            value={ips.liquidity}
            onChange={(v) => setIps({ liquidity: v })}
          />
        </IpsRow>
        <IpsRow k="Legal" sub="법적">
          <span className="text-[11px] font-semibold text-muted-foreground">
            {IPS_DEFAULT.legal}
          </span>
        </IpsRow>
        <IpsRow k="Unique" sub="특수" last>
          <span className="text-[11px] font-semibold text-muted-foreground">
            {IPS_DEFAULT.unique}
          </span>
        </IpsRow>
      </Card>

      <Button
        size="lg"
        className="w-full rounded-xl py-6 text-sm font-extrabold shadow-[0_4px_14px_rgba(0,100,255,0.28)]"
      >
        <Sparkles />
        분석하기
      </Button>
    </aside>
  );
}

function IpsRow({
  k,
  sub,
  last,
  children,
}: {
  k: string;
  sub: string;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`flex items-center gap-2 py-1.5 ${last ? "" : "border-b border-muted"}`}
    >
      <div className="w-14 shrink-0">
        <b className="block text-[11px] font-extrabold">{k}</b>
        <span className="block text-[8px] font-semibold leading-none text-muted-foreground">
          {sub}
        </span>
      </div>
      <div className="flex flex-1 items-center">{children}</div>
    </div>
  );
}

function Segment<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-1 gap-0.5 rounded-lg bg-muted p-0.5">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`flex-1 rounded-md py-1 text-[10px] font-bold transition-colors ${
            value === opt
              ? "bg-white text-brand-dark shadow-sm"
              : "text-muted-foreground"
          }`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
