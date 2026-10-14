import { PageShell } from "@/components/PageShell";
import { vi } from "@/i18n/vi";

export default function Page() {
  return <PageShell title={vi.review.title} description={vi.review.description} />;
}
