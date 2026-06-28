import type { Metadata } from "next";
import "./globals.css";
import IconRail from "@/components/IconRail";
import RightColumn from "@/components/RightColumn";

export const metadata: Metadata = {
  title: "LU · 涨停 limit-up",
  description: "AI 原生个人投资平台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className="font-sans antialiased">
        <div className="flex h-screen overflow-hidden">
          <IconRail />
          <RightColumn>{children}</RightColumn>
        </div>
      </body>
    </html>
  );
}
