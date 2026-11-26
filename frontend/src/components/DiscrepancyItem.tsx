import { Link } from "react-router-dom";
import { fmtDateTime } from "../api/format";
import type { DiscrepancyListItem } from "../api/types";
import { FileList } from "./Attachments";
import { DiscrepancyBadge } from "./StatusBadge";
import { CheckIcon, button } from "./ui";

/** One discrepancy with its PO/shipment context (dashboard and Discrepancies page). */
export default function DiscrepancyItem({ d, onResolve, compact = false }: { d: DiscrepancyListItem; onResolve?: () => void; compact?: boolean }) {
  return (
    <article className={`rounded-xl border px-4 py-3 ${d.status === "OPEN" ? "border-red-200 bg-red-50/50" : "border-slate-200 bg-white"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2">
            <DiscrepancyBadge type={d.type} status={d.status} />
            <Link to={`/pos/${d.po_id}`} className="font-bold text-brand-navy hover:text-brand-red">
              {d.po_number}
            </Link>
            <span className="text-sm text-slate-500">
              {d.shipment_no} · {d.vendor.name}
            </span>
          </p>
          {d.item_name && <p className="mt-1 text-sm font-semibold text-slate-700">{d.item_name}</p>}
        </div>
        {onResolve && d.status === "OPEN" && (
          <button type="button" className={button("red", "sm")} onClick={onResolve}>
            <CheckIcon className="h-3.5 w-3.5" />
            Resolve
          </button>
        )}
      </div>
      {d.description && <p className={`mt-1 whitespace-pre-line text-sm text-slate-700 ${compact ? "line-clamp-2" : ""}`}>{d.description}</p>}
      <p className="mt-1 text-xs text-slate-500">
        Reported {fmtDateTime(d.created_at)}
        {d.reported_by_name && ` by ${d.reported_by_name}`}
      </p>
      {!compact && d.attachments.length > 0 && (
        <div className="mt-2">
          <FileList files={d.attachments} />
        </div>
      )}
      {d.resolution_note && (
        <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <strong>Resolved</strong>
          {d.resolved_at && ` ${fmtDateTime(d.resolved_at)}`}
          {d.resolved_by_name && ` by ${d.resolved_by_name}`}: {d.resolution_note}
        </p>
      )}
    </article>
  );
}
