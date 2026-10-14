import Link from "next/link";

import { PageShell } from "@/components/PageShell";
import { vi } from "@/i18n/vi";

const areas = [
  { href: "/verify", label: vi.verify.title },
  { href: "/review", label: vi.review.title },
  { href: "/forensic", label: vi.forensic.title },
] as const;

export default function Home() {
  return (
    <PageShell title={vi.app.name}>
      <ul className="flex flex-col gap-2">
        {areas.map((a) => (
          <li key={a.href}>
            <Link className="underline" href={a.href}>
              {a.label}
            </Link>
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
