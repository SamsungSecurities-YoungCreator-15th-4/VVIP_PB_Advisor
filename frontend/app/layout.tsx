import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VVIP PB Advisor",
  description: "포트폴리오 제안 · 거시경제 스트레스 테스트",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
