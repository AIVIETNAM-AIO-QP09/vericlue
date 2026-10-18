import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageShell } from "@/components/PageShell";
import { vi } from "@/i18n/vi";

import { LabSession } from "./LabSession";

// Trang nội bộ cho người thử mô hình thật (ADR-0012): chỉ chạy ở `next dev`, mọi môi trường khác trả 404.
export const metadata: Metadata = {
  title: vi.lab.session.title,
  robots: { index: false, follow: false },
};

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  if (process.env.NODE_ENV !== "development") notFound();
  const { id } = await searchParams;
  return (
    <PageShell title={vi.lab.session.title} description={vi.lab.session.description}>
      <LabSession initialId={typeof id === "string" ? id : ""} />
    </PageShell>
  );
}
