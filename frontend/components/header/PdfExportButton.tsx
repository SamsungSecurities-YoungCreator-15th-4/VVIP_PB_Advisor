"use client";

import { useRef, useState } from "react";
import { ChevronDown, Eye, FileDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import PbPdfTemplate from "@/components/pdf/PbPdfTemplate";
import ClientPdfTemplate from "@/components/pdf/ClientPdfTemplate";

const isDev = process.env.NODE_ENV === "development";

type PdfType = "pb" | "client";

const FILE_NAMES: Record<PdfType, string> = {
  pb: "VVIP_상담리포트_PB용.pdf",
  client: "VVIP_상담리포트_고객용.pdf",
};

export default function PdfExportButton() {
  const [preview, setPreview] = useState<PdfType | null>(null);
  const [exporting, setExporting] = useState<PdfType | null>(null);

  const pbRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<HTMLDivElement>(null);

  async function handleExport(type: PdfType) {
    const el = type === "pb" ? pbRef.current : clientRef.current;
    if (!el) return;

    setExporting(type);
    try {
      const { domToCanvas } = await import("modern-screenshot");
      const { default: jsPDF } = await import("jspdf");

      // A4 기준: 794×1123px → 210×297mm
      const canvas = await domToCanvas(el, { scale: 2 });

      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
      const imgData = canvas.toDataURL("image/png");
      pdf.addImage(imgData, "PNG", 0, 0, 210, 297);
      pdf.save(FILE_NAMES[type]);
    } finally {
      setExporting(null);
    }
  }

  return (
    <>
      {/* ── off-screen 템플릿 컨테이너 ── */}
      <div
        aria-hidden="true"
        style={{ position: "fixed", left: -9999, top: 0, pointerEvents: "none", zIndex: -1 }}
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
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => handleExport("pb")}>
            <FileDown className="mr-1.5 size-3" />
            PB용 추출
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => handleExport("client")}>
            <FileDown className="mr-1.5 size-3" />
            고객용 추출
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

function DevPreviewModal({ type, onClose }: { type: PdfType; onClose: () => void }) {
  const PdfPreviewModal = require("@/components/pdf/PdfPreviewModal").default;
  return <PdfPreviewModal type={type} onClose={onClose} />;
}
