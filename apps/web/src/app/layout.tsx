import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "VeriClue",
  description: "Hệ thống xác minh danh tính điện tử VeriClue",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
