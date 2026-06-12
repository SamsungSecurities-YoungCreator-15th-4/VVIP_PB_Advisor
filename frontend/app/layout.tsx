import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VVIP PB Advisor",
  description: "PB가 VVIP 고객 상담 시 사용하는 AI 기반 자산관리 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css"
        />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
