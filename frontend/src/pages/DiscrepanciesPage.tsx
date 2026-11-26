import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import type { DiscrepancyListItem } from "../api/types";
import DiscrepancyItem from "../components/DiscrepancyItem";
import { ResolveModal } from "../components/PoActions";
import { Banner, Card, EmptyState, Loading } from "../components/ui";
import type { Notice } from "../components/ui";

type Tab = "OPEN" | "RESOLVED" | "";

/** Purchasing: every discrepancy Receiving declared, to follow up and resolve. */
export default function DiscrepanciesPage() {
  const [tab, setTab] = useState<Tab>("OPEN");
  const [items, setItems] = useState<DiscrepancyListItem[] | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [resolving, setResolving] = useState<DiscrepancyListItem | null>(null);

  const load = useCallback(() => {
    setItems(null);
    api<DiscrepancyListItem[]>(`/api/discrepancies${tab ? `?status=${tab}` : ""}`)
      .then(setItems)
      .catch((err) => setNotice({ type: "error", text: errorText(err) }));
  }, [tab]);
  useEffect(load, [load]);

  return (
    <Card
      eyebrow="Purchasing"
      title="Discrepancies"
      description="Short, extra, wrong or damaged goods reported by Receiving. Resolve each one once it is settled with the vendor."
    >
      <Banner notice={notice} />
      <div className="mb-5 inline-flex rounded-xl border border-blue-100 bg-brand-ice p-1" role="tablist">
        {(
          [
            ["OPEN", "Open"],
            ["RESOLVED", "Resolved"],
            ["", "All"],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`rounded-lg px-4 py-2 text-sm font-bold transition ${tab === value ? "bg-white text-brand-navy shadow-sm" : "text-slate-500 hover:text-brand-navy"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {!items && <Loading />}
      {items && items.length === 0 && (
        <EmptyState title={tab === "OPEN" ? "No open discrepancies" : "Nothing here yet"} text={tab === "OPEN" ? "Everything received so far matched, or has been resolved." : undefined} />
      )}
      {items && items.length > 0 && (
        <div className="space-y-3">
          {items.map((d) => (
            <DiscrepancyItem key={d.id} d={d} onResolve={() => setResolving(d)} />
          ))}
        </div>
      )}

      {resolving && (
        <ResolveModal
          discrepancy={resolving}
          onClose={() => setResolving(null)}
          onDone={() => {
            setResolving(null);
            setNotice({ type: "success", text: `Discrepancy on ${resolving.po_number} resolved. The vendor has been notified.` });
            load();
          }}
        />
      )}
    </Card>
  );
}
