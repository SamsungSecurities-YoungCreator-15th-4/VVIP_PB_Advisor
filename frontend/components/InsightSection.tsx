"use client";

import { useState } from "react";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { INSIGHT } from "@/lib/mockData";

/** 우측 하단: AI 인사이트 검색 + 결과 + 출처/인용 목록 (RAG 연동 전 골격) */
export default function InsightSection() {
  const [query, setQuery] = useState("");

  return (
    <Card className="flex-1 gap-0 p-3.5">
      <p className="mb-2.5 text-[13px] font-bold">AI 인사이트</p>
      <form
        className="mb-2.5 flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          // TODO: 백엔드 RAG 검색 연동 (lib/api.ts apiPost 사용 예정)
        }}
      >
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={INSIGHT.placeholder}
          className="h-8 text-[11px]"
        />
        <Button type="submit" size="sm" className="font-bold">
          검색
        </Button>
      </form>

      <p className="text-[11px] font-medium leading-relaxed text-muted-foreground">
        {INSIGHT.defaultAnswer}
      </p>

      <p className="mb-1 mt-4 text-[13px] font-bold">출처 / 인용 목록</p>
      <div>
        {INSIGHT.sources.map((src) => (
          <div
            key={src.title}
            className="flex items-center gap-2 border-b border-muted py-2 last:border-none"
          >
            <FileText className="size-3.5 shrink-0 text-muted-foreground/60" />
            <span className="flex-1 text-[11px] font-bold text-muted-foreground">
              {src.title}
            </span>
            <span className="text-[9.5px] font-semibold tabular-nums text-muted-foreground/60">
              {src.date}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
