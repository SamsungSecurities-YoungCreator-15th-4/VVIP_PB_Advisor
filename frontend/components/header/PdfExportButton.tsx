"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import { ChevronDown, Eye, FileDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import PdfPreviewModal from "@/components/pdf/PdfPreviewModal";
import { useDashboardStore } from "@/lib/store";

// SSR 비활성화 — new Date() hydration mismatch 방지
const PbPdfTemplate = dynamic(() => import("@/components/pdf/PbPdfTemplate"), {
  ssr: false,
});
const ClientPdfTemplate = dynamic(
  () => import("@/components/pdf/ClientPdfTemplate"),
  { ssr: false },
);

const isDev = process.env.NODE_ENV === "development";

type PdfType = "pb" | "client";

function getFileName(type: PdfType, name: string): string {
  const date = new Date()
    .toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit" })
    .replace(/\. /g, "")
    .replace(/\.$/, "");
  const label = type === "pb" ? "PB용" : "고객용";
  return `VVIP_상담리포트_${label}_${name}_${date}.pdf`;
}

export default function PdfExportButton() {
  const [preview, setPreview] = useState<PdfType | null>(null);
  const [exporting, setExporting] = useState<PdfType | null>(null);

  // 파일명은 PDF 표지·헤더와 동일하게 현재 선택된 고객을 따른다.
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  const selectedCustomer =
    customers.find((c) => c.id === selectedCustomerId) ?? customers[0];

  const pbRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<HTMLDivElement>(null);

  async function handleExport(type: PdfType) {
    const container = type === "pb" ? pbRef.current : clientRef.current;
    if (!container) return;

    setExporting(type);
    try {
      const { domToCanvas } = await import("modern-screenshot");
      const { default: jsPDF } = await import("jspdf");

      const pdf = new jsPDF({
        orientation: "portrait",
        unit: "mm",
        format: "a4",
      });

      // data-pdf-page 속성이 있는 요소를 페이지 단위로 캡처
      const pages = container.querySelectorAll<HTMLElement>("[data-pdf-page]");

      if (pages.length === 0) {
        // fallback: 단일 이미지로 전체 캡처 (A4 1장)
        const canvas = await domToCanvas(container, { scale: 2 });
        pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, 210, 297);
      } else {
        for (let i = 0; i < pages.length; i++) {
          const canvas = await domToCanvas(pages[i], { scale: 2 });
          if (i > 0) pdf.addPage();
          pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, 210, 297);
        }
      }

      pdf.save(getFileName(type, selectedCustomer.name));
    } finally {
      setExporting(null);
    }
  }

  return (
    <>
      {/* ── off-screen 템플릿 컨테이너 (dynamic ssr:false — hydration mismatch 방지) ── */}
      <div
        aria-hidden="true"
        style={{
          position: "fixed",
          left: -9999,
          top: 0,
          pointerEvents: "none",
          zIndex: -1,
        }}
      >
        <div ref={pbRef}>
          <PbPdfTemplate />
        </div>
        <div ref={clientRef}>
          <ClientPdfTemplate />
        </div>
      </div>

      {/* ── 드롭다운 버튼 ── */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button className="shrink-0 font-bold" disabled={!!exporting}>
            {exporting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileDown className="size-4" />
            )}
            <span className="hidden sm:inline">
              {exporting ? "생성 중..." : "PDF 추출"}
            </span>
            <ChevronDown className="size-3 opacity-70" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onSelect={() => handleExport("pb")}>
            PB용
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => handleExport("client")}>
            고객용
          </DropdownMenuItem>

          {isDev && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => setPreview("pb")}
                className="text-blue-600"
              >
                <Eye className="mr-1.5 size-3" />
                PB용 미리보기 (dev)
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => setPreview("client")}
                className="text-blue-600"
              >
                <Eye className="mr-1.5 size-3" />
                고객용 미리보기 (dev)
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {isDev && preview && (
        <DevPreviewModal type={preview} onClose={() => setPreview(null)} />
      )}
    </>
  );
}

function DevPreviewModal({
  type,
  onClose,
}: {
  type: PdfType;
  onClose: () => void;
}) {
  return <PdfPreviewModal type={type} onClose={onClose} />;
}
