import { PageShell } from "@/components/PageShell";
import { vi } from "@/i18n/vi";

import { VerifyFlow } from "./VerifyFlow";

export default function Page() {
  return (
    <PageShell title={vi.verify.title} description={vi.verify.description}>
      <VerifyFlow />
    </PageShell>
  );
}
