"use client";

// Trang thử nội bộ: hiện kết quả từng module của một phiên, đọc từ API bàn duyệt có sẵn.
// Không thuộc luồng người dân. Ý kiến AI của bàn duyệt chỉ mở sau quyết định ban đầu, nên nếu chưa có
// thì nút bên dưới ghi quyết định thử với ghi chú "dev-test".

import { useCallback, useEffect, useMemo, useState } from "react";

import { vi } from "@/i18n/vi";
import { ApiError, createApiClient, type ReviewAiOpinion } from "@/lib/api/client";

const t = vi.lab.session;

type Load =
  | { step: "idle" }
  | { step: "loading" }
  | { step: "not_found" }
  | { step: "need_initial"; caseId: string }
  | { step: "done"; opinion: ReviewAiOpinion }
  | { step: "error" };

type Evidence = { name?: unknown; value?: unknown; label_vi?: unknown; unit?: unknown };

function show(value: unknown): string {
  if (value === null || value === undefined) return t.none;
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function evidenceLine(item: Evidence): string {
  const label = typeof item.label_vi === "string" ? item.label_vi : show(item.name);
  const unit = typeof item.unit === "string" ? ` ${item.unit}` : "";
  return `${label}: ${show(item.value)}${unit}`;
}

export function LabSession({ initialId }: { initialId: string }) {
  const client = useMemo(() => createApiClient(), []);
  const [id, setId] = useState(initialId);
  const [load, setLoad] = useState<Load>(initialId ? { step: "loading" } : { step: "idle" });

  const fetchOpinion = useCallback(
    async (caseId: string): Promise<Load> => {
      try {
        return { step: "done", opinion: await client.getAiOpinion(caseId) };
      } catch (e) {
        if (e instanceof ApiError && e.errorCode === "initial_decision_required") {
          return { step: "need_initial", caseId };
        }
        return { step: "error" };
      }
    },
    [client],
  );

  // Tìm ca theo mã ca hoặc mã phiên rồi lấy ý kiến AI. Hàm thuần (không setState) để effect gọi được.
  const resolve = useCallback(
    async (wanted: string): Promise<Load> => {
      try {
        const { items } = await client.listReviewCases();
        const found = items.find((c) => c.case_id === wanted || c.session_id === wanted);
        return found ? await fetchOpinion(found.case_id) : { step: "not_found" };
      } catch {
        return { step: "error" };
      }
    },
    [client, fetchOpinion],
  );

  useEffect(() => {
    const wanted = initialId.trim();
    if (!wanted) return;
    let cancelled = false;
    void resolve(wanted).then((result) => {
      if (!cancelled) setLoad(result);
    });
    return () => {
      cancelled = true;
    };
  }, [initialId, resolve]);

  const submit = useCallback(async () => {
    const wanted = id.trim();
    if (!wanted) return;
    setLoad({ step: "loading" });
    setLoad(await resolve(wanted));
  }, [id, resolve]);

  const recordInitial = useCallback(
    async (caseId: string) => {
      setLoad({ step: "loading" });
      try {
        await client.recordInitialDecision(caseId, "request_retry", "dev-test");
        setLoad(await fetchOpinion(caseId));
      } catch {
        setLoad({ step: "error" });
      }
    },
    [client, fetchOpinion],
  );

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <label className="flex flex-col gap-1">
          <span>{t.idLabel}</span>
          <input
            value={id}
            onChange={(e) => setId(e.target.value)}
            className="rounded border px-2 py-1"
            size={36}
          />
        </label>
        <button type="submit" className="rounded bg-blue-600 px-4 py-2 text-white">
          {t.load}
        </button>
      </form>

      {load.step === "idle" && !initialId && <p>{t.missingId}</p>}
      {load.step === "loading" && <p role="status">{t.loading}</p>}
      {load.step === "not_found" && <p role="status">{t.notFound}</p>}
      {load.step === "error" && <p role="alert">{t.error}</p>}
      {load.step === "need_initial" && (
        <div className="flex flex-col gap-2">
          <p>{t.needInitial}</p>
          <button
            type="button"
            onClick={() => void recordInitial(load.caseId)}
            className="self-start rounded border px-4 py-2"
          >
            {t.recordInitial}
          </button>
        </div>
      )}

      {load.step === "done" && (
        <div className="flex flex-col gap-3">
          <p>
            {t.suggestion}: <strong>{load.opinion.suggestion}</strong>
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  {[t.module, t.status, t.gate, t.score, t.probAttack, t.version, t.latency].map(
                    (h) => (
                      <th key={h} className="px-2 py-1">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {load.opinion.modules.map((m, index) => (
                  <tr key={`${show(m.module)}-${index}`} className="border-b align-top">
                    <td className="px-2 py-1 font-medium">{show(m.module)}</td>
                    <td className="px-2 py-1">{show(m.status)}</td>
                    <td className="px-2 py-1">{show(m.gate)}</td>
                    <td className="px-2 py-1">{show(m.score)}</td>
                    <td className="px-2 py-1">{show(m.prob_attack)}</td>
                    <td className="px-2 py-1">{show(m.model_version)}</td>
                    <td className="px-2 py-1">{show(m.latency_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {load.opinion.modules.map((m, index) => {
            const items = Array.isArray(m.evidence) ? (m.evidence as Evidence[]) : [];
            if (items.length === 0) return null;
            return (
              <section key={`ev-${show(m.module)}-${index}`}>
                <h3 className="font-semibold">
                  {t.evidence} — {show(m.module)}
                </h3>
                <ul className="list-disc pl-5 text-sm">
                  {items.map((item, i) => (
                    <li key={i}>{evidenceLine(item)}</li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
