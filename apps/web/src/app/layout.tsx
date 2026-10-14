import type { Metadata } from "next";
import type { ReactNode } from "react";

import { vi } from "@/i18n/vi";

import "./globals.css";

export const metadata: Metadata = {
  title: vi.app.name,
  description: vi.app.description,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="vi" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
