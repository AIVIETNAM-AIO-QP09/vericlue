import type { Metadata } from "next";

import { PageShell } from "@/components/PageShell";
import { vi } from "@/i18n/vi";

import { ChromaPulseLab } from "./ChromaPulseLab";

// Trang nội bộ cho CAP-03: không để công cụ tìm kiếm lập chỉ mục.
export const metadata: Metadata = {
  title: vi.lab.chromapulse.title,
  robots: { index: false, follow: false },
};

export default function Page() {
  return (
    <PageShell title={vi.lab.chromapulse.title} description={vi.lab.chromapulse.description}>
      <ChromaPulseLab />
    </PageShell>
  );
}
