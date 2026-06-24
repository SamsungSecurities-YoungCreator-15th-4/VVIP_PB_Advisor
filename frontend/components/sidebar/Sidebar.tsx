"use client";

import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Loader2,
  Mic,
  PanelLeftClose,
  PanelLeftOpen,
  RotateCcw,
  Upload,
  UserPlus,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import DataSourceBadge from "@/components/common/DataSourceBadge";
import StressTestSection from "@/components/right-panel/StressTestSection";
import { type Customer, CUSTOMERS, PAST_CONSULTATIONS } from "@/lib/mockData";
import {
  type ListedClient,
  createClient,
  listClients,
  uploadSttConsultation,
} from "@/lib/api";
import { useDashboardStore } from "@/lib/store";
import { useAutoCollapse } from "@/lib/useAutoCollapse";
import { useSttRealtime } from "@/lib/useSttRealtime";

const DEFAULT_CLIENT_TAX_PROFILE = {
  isaUsedManwon: 0,
  pensionUsedManwon: 0,
  realizedLossManwon: 0,
  marginalRatePct: 38.5,
  age: 50,
  horizonYears: 10,
  nearTermNeedManwon: 0,
  nearTermNeedYears: null,
  isaOpened: true,
} satisfies Pick<
  Customer,
  | "isaUsedManwon"
  | "pensionUsedManwon"
  | "realizedLossManwon"
  | "marginalRatePct"
  | "age"
  | "horizonYears"
  | "nearTermNeedManwon"
  | "nearTermNeedYears"
  | "isaOpened"
>;

function toDashboardCustomer(client: ListedClient): Customer {
  const persona = CUSTOMERS.find((c) => c.name === client.name);
  const safeClientId = client.clientId || "";
  const displayId = safeClientId || `client-${client.name || "unknown"}`;
  const aumEokwon =
    client.aumEokwon > 0 ? client.aumEokwon : (persona?.aumEokwon ?? 0);

  return {
    ...(persona ?? DEFAULT_CLIENT_TAX_PROFILE),
    id: displayId,
    name: client.name || "Unknown",
    grade: "VVIP",
    pbCode: persona?.pbCode ?? `PB-${displayId.slice(0, 6).toUpperCase()}`,
    aumLabel: aumEokwon > 0 ? `운용자산 ${aumEokwon}억원` : "운용자산 미입력",
    aumEokwon,
    clientId: safeClientId || undefined,
    persisted: true,
  };
}

/** 좌측 사이드바: 고객 선택 · 상담 입력 · 상담 내역 · IPS 조율기 · 분석하기 */
export default function Sidebar() {
  const {
    customers,
    selectedCustomerId,
    ips,
    setIps,
    selectCustomer,
    addCustomer,
    setCustomers,
    transcript,
    transcriptSource,
    sttStatus,
    sttNote,
    setTranscript,
    setConsultationId,
    setSttStatus,
  } = useDashboardStore();
  const customer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];

  const [isOpen, setIsOpen] = useAutoCollapse(1024);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAum, setNewAum] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const {
    status: realtimeStatus,
    errorMsg: realtimeError,
    start: startRealtime,
    stop: stopRealtime,
  } = useSttRealtime();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);

  // 드롭다운을 Card의 overflow-hidden 밖에 fixed로 띄우기 위해 트리거 위치를 기억
  const dropdownTriggerRef = useRef<HTMLButtonElement>(null);
  const [dropdownRect, setDropdownRect] = useState<DOMRect | null>(null);

  // 드롭다운이 열린 상태에서 스크롤·리사이즈 시 자동 닫기 (fixed 드롭다운 위치 이탈 방지)
  useEffect(() => {
    if (!dropdownOpen) return;
    const close = () => setDropdownOpen(false);
    window.addEventListener("scroll", close, { capture: true, passive: true });
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [dropdownOpen]);

  useEffect(() => {
    let cancelled = false;
    async function hydrateClients() {
      const result = await listClients();
      if (cancelled || result.source !== "live" || result.data.length === 0) {
        return;
      }
      setCustomers(result.data.map(toDashboardCustomer));
    }

    void hydrateClients();
    return () => {
      cancelled = true;
    };
  }, [setCustomers]);

  if (!customer) return null;

  const handleDropdownToggle = () => {
    if (!dropdownOpen && dropdownTriggerRef.current) {
      setDropdownRect(dropdownTriggerRef.current.getBoundingClientRect());
    }
    setDropdownOpen((o) => !o);
  };

  // 고객 추가 → POST /clients(DB 저장). 성공 시 실 client_id 보유 고객으로 추가·선택.
  // 동명이인(409)·입력오류(422)는 서버 거절로 보고 로컬 추가하지 않는다.
  // 저장 실패(네트워크/5xx)는 데모로만 로컬 추가하고 "저장 안 됨" 배지로 명시한다.
  const handleAddCustomer = async () => {
    const name = newName.trim();
    if (!name || addLoading) return;
    const aumVal = Math.max(0, parseFloat(newAum) || 0);

    setAddLoading(true);
    setAddError(null);
    const result = await createClient(name, aumVal);
    setAddLoading(false);

    if (result.status === "conflict" || result.status === "invalid") {
      setAddError(result.message);
      return; // 로컬 추가하지 않음
    }

    const persisted = result.status === "live";
    const id = result.data.clientId || `cust-${Date.now()}`;
    addCustomer({
      id,
      name,
      grade: "VVIP",
      pbCode: `PB-${Math.floor(100000 + Math.random() * 900000)}`,
      aumLabel: aumVal > 0 ? `운용자산 ${aumVal}억원` : "운용자산 미입력",
      aumEokwon: aumVal,
      // 절세계좌·적합성 입력값은 신규 고객 등록 시 미상 — 기본값으로 시작(추후 PB 입력/DB 연동)
      isaUsedManwon: 0,
      pensionUsedManwon: 0,
      realizedLossManwon: 0,
      marginalRatePct: 38.5,
      age: 50,
      horizonYears: 10,
      nearTermNeedManwon: 0,
      nearTermNeedYears: null,
      isaOpened: true,
      clientId: result.data.clientId || undefined,
      persisted,
    });
    selectCustomer(id); // 추가한 고객을 바로 선택 → STT 업로드가 이 고객으로 진행
    setNewName("");
    setNewAum("");
    setAddModalOpen(false);
  };

  // 음성 업로드 → STT(/consultations/stt) → 전사·IPS 갱신. 실패 시 mock 폴백(배지).
  const handleTranscribe = async () => {
    if (!uploadedFile || sttStatus === "uploading") return;
    setSttStatus("uploading");
    const res = await uploadSttConsultation(customer.name, uploadedFile);
    setTranscript(res.data.transcript, res.source);
    setConsultationId(res.data.consultationId);
    // 추출된 IPS 값만 조율기에 반영(없는 값은 기존 유지).
    if (Object.keys(res.data.ips).length > 0) setIps(res.data.ips);
    if (res.source === "live") {
      setSttStatus("done");
    } else {
      setSttStatus("error", res.note);
    }
  };

  // 사이드바가 닫혔을 때: 하나의 패널임을 시각적으로 표현하는 좁은 카드 스트립
  if (!isOpen) {
    return (
      <div className="flex w-10 self-start shrink-0 flex-col items-center rounded-2xl bg-card py-3 ring-1 ring-foreground/10">
        <button
          onClick={() => setIsOpen(true)}
          title="사이드바 열기"
          className="flex flex-col items-center gap-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <PanelLeftOpen className="size-4" />
        </button>
      </div>
    );
  }

  return (
    <>
      <aside className="flex w-[300px] shrink-0 flex-col gap-2.5 rounded-2xl bg-card p-2.5 ring-1 ring-foreground/10">
        {/* 패널 헤더 */}
        <div className="flex items-center px-0.5 pb-0.5">
          <button
            onClick={() => setIsOpen(false)}
            title="사이드바 닫기"
            className="rounded p-0.5 text-muted-foreground hover:text-foreground"
          >
            <PanelLeftClose className="size-4" />
          </button>
        </div>

        {/* 고객 선택 */}
        <Card className="gap-0 p-3">
          <div className="mb-2">
            <p className="text-[14px] font-bold">고객 선택</p>
          </div>

          {/* 드롭다운 트리거 */}
          <button
            ref={dropdownTriggerRef}
            type="button"
            onClick={handleDropdownToggle}
            className="flex w-full items-center gap-3 rounded-xl px-1 py-1 hover:bg-muted"
          >
            <div className="flex size-11 items-center justify-center rounded-xl bg-linear-to-br from-[#DCE9FF] to-[#B8D4FF] text-lg font-extrabold text-brand-dark">
              {customer.name[0]}
            </div>
            <div className="flex-1 text-left">
              <div className="flex items-center gap-2 text-[15px] font-extrabold">
                {customer.name}
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground">
                <span>{customer.aumLabel}</span>
                {customer.persisted === false && (
                  <DataSourceBadge
                    source="fallback"
                    note="DB 저장 실패 — 데모로만 추가된 고객입니다."
                  />
                )}
              </div>
            </div>
            <ChevronDown
              className={`size-4 shrink-0 text-muted-foreground transition-transform ${
                dropdownOpen ? "rotate-180" : ""
              }`}
            />
          </button>
        </Card>

        {/* 상담 입력 */}
        <Card className="gap-0 p-3">
          <p className="mb-2 text-[14px] font-bold">상담 입력</p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".wav"
            className="hidden"
            onChange={(e) => setUploadedFile(e.target.files?.[0] ?? null)}
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 rounded-xl border-[1.5px] border-dashed border-[#B8D4FF] bg-brand/5 px-3 py-1 text-center"
            >
              <span className="mx-auto mb-1 flex size-8 items-center justify-center rounded-full border border-[#DCE9FF] bg-white">
                <Upload className="size-4 text-brand" />
              </span>
              <span className="block text-[13px] font-bold text-brand-dark">
                음성 업로드
              </span>
              {uploadedFile ? (
                <span className="mt-0.5 block truncate text-[10px] font-semibold text-brand">
                  {uploadedFile.name}
                </span>
              ) : (
                <span className="mt-0.5 block text-[10px] font-semibold text-muted-foreground">
                  wav 파일
                </span>
              )}
            </button>

            <button
              type="button"
              disabled={
                !customer.clientId ||
                realtimeStatus === "connecting" ||
                realtimeStatus === "stopping"
              }
              onClick={() => {
                if (!customer.clientId) return;
                if (realtimeStatus === "recording") {
                  stopRealtime();
                } else if (
                  realtimeStatus === "idle" ||
                  realtimeStatus === "done" ||
                  realtimeStatus === "error"
                ) {
                  void startRealtime(customer.clientId);
                }
              }}
              className={`flex-1 rounded-xl border-[1.5px] border-dashed px-3 py-1 text-center disabled:cursor-not-allowed disabled:opacity-50 ${
                realtimeStatus === "recording"
                  ? "border-red-400 bg-red-50"
                  : "border-[#B8D4FF] bg-brand/5"
              }`}
            >
              <span
                className={`mx-auto mb-1 flex size-8 items-center justify-center rounded-full border ${
                  realtimeStatus === "recording"
                    ? "border-red-200 bg-red-50"
                    : "border-[#DCE9FF] bg-white"
                }`}
              >
                {realtimeStatus === "connecting" ||
                realtimeStatus === "stopping" ? (
                  <Loader2 className="size-4 animate-spin text-brand" />
                ) : (
                  <Mic
                    className={`size-4 ${
                      realtimeStatus === "recording"
                        ? "animate-pulse text-red-500"
                        : "text-brand"
                    }`}
                  />
                )}
              </span>
              <span
                className={`block text-[13px] font-bold ${
                  realtimeStatus === "recording"
                    ? "text-red-600"
                    : "text-brand-dark"
                }`}
              >
                {realtimeStatus === "connecting"
                  ? "연결 중..."
                  : realtimeStatus === "recording"
                    ? "녹음 중"
                    : realtimeStatus === "stopping"
                      ? "처리 중..."
                      : "실시간 녹음"}
              </span>
              <span className="mt-0.5 block text-[10px] font-semibold text-muted-foreground">
                {realtimeStatus === "recording"
                  ? "클릭해 종료"
                  : customer.clientId
                    ? "WebSocket STT"
                    : "DB 고객 필요"}
              </span>
            </button>
          </div>

          {uploadedFile && (
            <Button
              size="sm"
              className="mt-2 w-full font-bold"
              onClick={handleTranscribe}
              disabled={sttStatus === "uploading"}
            >
              {sttStatus === "uploading" ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  전사·분석 중…
                </>
              ) : (
                "전사 시작"
              )}
            </Button>
          )}
          {(sttStatus === "done" || realtimeStatus === "done") && (
            <p className="mt-1.5 text-[10px] font-semibold text-emerald-600">
              전사 완료 — 상담 내역·IPS 조율기에 반영했습니다.
            </p>
          )}
          {sttStatus === "error" && (
            <p className="mt-1.5 text-[10px] font-semibold text-amber-600">
              {sttNote ?? "전사에 실패해 데모 데이터를 표시합니다."}
            </p>
          )}
          {realtimeStatus === "error" && realtimeError && (
            <p className="mt-1.5 text-[10px] font-semibold text-amber-600">
              {realtimeError}
            </p>
          )}
        </Card>

        {/* 상담 내역 */}
        <Card className="gap-0 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[14px] font-bold">상담 내역</p>
            <DataSourceBadge source={transcriptSource} note={sttNote} />
          </div>
          <div className="flex max-h-[150px] flex-col gap-1.5 overflow-y-auto pr-0.5">
            {transcript.map((m, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <span
                  className={`mt-0.5 inline-flex w-7 shrink-0 items-center justify-center rounded-md py-0.5 text-[8.5px] font-extrabold ${
                    m.speaker === "고객"
                      ? "bg-[#DCE9FF] text-brand-dark"
                      : "bg-[#ADB5BD] text-white"
                  }`}
                >
                  {m.speaker}
                </span>
                <span className="flex-1 text-[13px] font-medium leading-snug text-muted-foreground">
                  {m.text}
                </span>
                <span className="mt-0.5 shrink-0 text-[9px] font-semibold tabular-nums text-muted-foreground/60">
                  {m.time}
                </span>
              </div>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-2 w-full border-muted font-bold text-foreground/60 hover:text-foreground/60"
            onClick={() => setHistoryOpen(true)}
          >
            <RotateCcw />
            지난 상담기록 불러오기
          </Button>
        </Card>

        {/* IPS 조율기 */}
        <Card className="flex-1 gap-0 p-3">
          <div className="mb-1">
            <p className="text-[14px] font-bold">IPS 조율기</p>
          </div>
          <IpsRow k="Goal" sub="목표">
            <Input
              value={ips.goal}
              onChange={(e) => setIps({ goal: e.target.value })}
              className="h-6 text-[13px] md:text-[13px]"
            />
          </IpsRow>
          <IpsRow k="Asset" sub="자산">
            <span className="text-[13px] font-extrabold tabular-nums text-brand-dark">
              {customer.aumEokwon}억원
            </span>
          </IpsRow>
          <IpsRow k="Return" sub="수익">
            <div className="flex flex-1 items-center gap-2">
              <span className="w-8 text-[13px] font-extrabold tabular-nums text-brand-dark">
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
              <span className="w-8 text-[13px] font-extrabold tabular-nums text-brand-dark">
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
            <Input
              value={ips.tax}
              onChange={(e) => setIps({ tax: e.target.value })}
              className="h-6 text-[13px] md:text-[13px]"
            />
          </IpsRow>
          <IpsRow k="Liquid" sub="유동성">
            <Segment
              options={["낮음", "중간", "높음"] as const}
              value={ips.liquidity}
              onChange={(v) => setIps({ liquidity: v })}
            />
          </IpsRow>
          <IpsRow k="Legal" sub="법적">
            <Input
              value={ips.legal}
              onChange={(e) => setIps({ legal: e.target.value })}
              className="h-6 text-[13px] md:text-[13px]"
            />
          </IpsRow>
          <IpsRow k="Unique" sub="특수" last>
            <Input
              value={ips.unique}
              onChange={(e) => setIps({ unique: e.target.value })}
              className="h-6 text-[13px] md:text-[13px]"
            />
          </IpsRow>
        </Card>

        <StressTestSection />

        <Button
          size="lg"
          className="w-full rounded-xl py-6 text-sm font-extrabold shadow-[0_4px_14px_rgba(0,100,255,0.28)]"
        >
          분석하기
        </Button>
      </aside>

      {/* ── 고객 드롭다운 (Card overflow-hidden 밖에 fixed로 렌더링) ── */}
      {dropdownOpen && dropdownRect && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setDropdownOpen(false)}
          />
          <div
            className="fixed z-50 overflow-hidden rounded-xl border bg-card shadow-xl"
            style={{
              top: dropdownRect.bottom + 4,
              left: dropdownRect.left,
              width: dropdownRect.width,
            }}
          >
            {customers.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  selectCustomer(c.id);
                  setDropdownOpen(false);
                }}
                className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left hover:bg-muted ${
                  c.id === selectedCustomerId ? "bg-brand/5" : ""
                }`}
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-linear-to-br from-[#DCE9FF] to-[#B8D4FF] text-sm font-extrabold text-brand-dark">
                  {c.name[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 text-[13px] font-extrabold">
                    {c.name}
                    {c.persisted === false && (
                      <DataSourceBadge
                        source="fallback"
                        note="DB 저장 실패 — 데모로만 추가된 고객입니다."
                      />
                    )}
                  </div>
                  <div className="text-[10px] font-semibold text-muted-foreground">
                    {c.aumLabel}
                  </div>
                </div>
                {c.id === selectedCustomerId && (
                  <span className="shrink-0 text-[9px] font-bold text-brand">
                    선택됨
                  </span>
                )}
              </button>
            ))}
            <div className="border-t p-1">
              <button
                type="button"
                onClick={() => {
                  setDropdownOpen(false);
                  setAddError(null);
                  setAddModalOpen(true);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-bold text-brand hover:bg-brand/5"
              >
                <UserPlus className="size-3.5" />
                고객 추가
              </button>
            </div>
          </div>
        </>
      )}

      {/* ── 지난 기록 모달 ── */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-[440px] rounded-2xl bg-card p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[15px] font-extrabold">지난 상담 기록</h3>
              <button
                onClick={() => setHistoryOpen(false)}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="flex max-h-[320px] flex-col gap-1.5 overflow-y-auto">
              {PAST_CONSULTATIONS.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between rounded-xl border px-3 py-2"
                >
                  <span className="text-[13px] font-semibold">{c.title}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 shrink-0 text-[11px] font-bold"
                    onClick={() => setHistoryOpen(false)}
                  >
                    불러오기
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── 고객 추가 모달 ── */}
      {addModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-[360px] rounded-2xl bg-card p-5 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-[15px] font-extrabold">고객 추가</h3>
              <button
                onClick={() => {
                  setAddModalOpen(false);
                  setAddError(null);
                }}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                  고객명
                </label>
                <Input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="예: 홍길동"
                  onKeyDown={(e) => e.key === "Enter" && handleAddCustomer()}
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-bold text-muted-foreground">
                  운용자산 (억원)
                </label>
                <Input
                  type="number"
                  value={newAum}
                  onChange={(e) => setNewAum(e.target.value)}
                  placeholder="예: 20"
                />
              </div>
              {addError && (
                <p className="text-[11px] font-semibold text-amber-600">
                  {addError}
                </p>
              )}
              <Button
                onClick={handleAddCustomer}
                className="w-full font-bold"
                disabled={!newName.trim() || addLoading}
              >
                {addLoading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    저장 중…
                  </>
                ) : (
                  "추가하기"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
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
        <b className="block text-[13px] font-extrabold">{k}</b>
        <span className="block text-[10px] font-semibold leading-none text-muted-foreground">
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
          className={`flex-1 rounded-md py-1 text-[13px] font-bold transition-colors ${
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
