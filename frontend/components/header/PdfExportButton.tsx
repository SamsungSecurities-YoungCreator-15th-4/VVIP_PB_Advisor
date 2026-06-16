"use client";

import { ChevronDown, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function PdfExportButton() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="shrink-0 font-bold">
          <FileDown className="size-4" />
          <span className="hidden sm:inline">PDF 추출</span>
          <ChevronDown className="size-3 opacity-70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => {}}>PB용</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => {}}>고객용</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
