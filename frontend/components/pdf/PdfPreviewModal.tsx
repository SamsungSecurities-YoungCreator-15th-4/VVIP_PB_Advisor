"use client";

/**
 * 개발 전용 PDF 미리보기 모달.
 * NODE_ENV === "development" 일 때만 렌더링되므로
 * 프로덕션 빌드에서는 이 컴포넌트가 완전히 제거된다.
 */

import { X } from "lucide-react";
import PbPdfTemplate from "@/components/pdf/PbPdfTemplate";
import ClientPdfTemplate from "@/components/pdf/ClientPdfTemplate";

type PdfType = "pb" | "client";

interface Props {
  type: PdfType;
  onClose: () => void;
}

export default function PdfPreviewModal({ type, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 py-8"
      onClick={onClose}
    >
      <div className="relative" onClick={(e) => e.stopPropagation()}>
        {/* 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute -top-8 right-0 flex items-center gap-1 rounded-md bg-white/20 px-2 py-1 text-[11px] font-bold text-white hover:bg-white/30"
        >
          <X className="size-3" />
          닫기 (ESC)
        </button>

        {/* 타입 배지 */}
        <div className="mb-2 flex items-center gap-2">
          <span className="rounded-md bg-white/20 px-2 py-0.5 text-[10px] font-bold text-white">
            {type === "pb" ? "📋 PB용 미리보기" : "👤 고객용 미리보기"}
          </span>
          <span className="text-[9px] text-white/60">개발 환경 전용 · 프로덕션에서는 표시되지 않음</span>
        </div>

        {/* 템플릿 렌더링 */}
        <div className="overflow-hidden rounded-xl shadow-2xl">
          {type === "pb" ? <PbPdfTemplate /> : <ClientPdfTemplate />}
        </div>
      </div>
    </div>
  );
}
