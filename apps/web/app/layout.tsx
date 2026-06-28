import type { Metadata } from "next";
import "./globals.css";
import IconRail from "@/components/IconRail";
import Topbar from "@/components/Topbar";
import StatusBar from "@/components/StatusBar";

export const metadata: Metadata = {
  title: "limit-up (LU)",
  description: "AI-native personal investment platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh">
      <body className="font-sans antialiased">
        <div className="flex h-screen overflow-hidden">
          <IconRail />
          <div className="flex-1 flex flex-col min-w-0">
            <Topbar />
            <main className="flex-1 min-h-0 overflow-hidden flex">{children}</main>
            <StatusBar />
          </div>
        </div>
      </body>
    </html>
  );
}
