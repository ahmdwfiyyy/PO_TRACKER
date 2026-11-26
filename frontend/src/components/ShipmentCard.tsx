import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { fmtDate, fmtDateTime, qty } from "../api/format";
import type { Shipment } from "../api/types";
import { FileList } from "./Attachments";
import { DiscrepancyBadge, Flags, ShipmentStatusBadge } from "./StatusBadge";
import { Badge, TruckIcon } from "./ui";

/** One shipment: what was sent, what arrived, documents, photos and discrepancies. */
export default function ShipmentCard({
  shipment: s,
  showPo = false,
  actions,
}: {
  shipment: Shipment;
  showPo?: boolean;
  actions?: ReactNode;
}) {
  const received = new Map(s.receipt?.items.map((r) => [r.po_item_id, r]) ?? []);

  return (
    <article className="rounded-xl border border-blue-100 bg-white">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-blue-50 px-4 py-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-bold text-brand-navy">
            <TruckIcon className="h-5 w-5 text-brand-blue" />
            {s.shipment_no}
            {s.is_partial && <Badge tone="violet">Partial</Badge>}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            {showPo && (
              <>
                <Link to={`/pos/${s.po_id}`} className="font-semibold text-brand-blue hover:text-brand-red">
                  {s.po_number}
                </Link>
                {" · "}
                {s.vendor.name}
                {" · "}
              </>
            )}
            {s.courier ?? "Courier not given"}
            {s.tracking_number && ` · ${s.tracking_number}`}
          </p>
          <p className={`text-xs ${s.overdue ? "font-bold text-brand-red" : "text-slate-500"}`}>
            Expected {fmtDate(s.expected_delivery_date)} · dispatched {fmtDateTime(s.dispatched_at)}
            {s.created_by_name && ` by ${s.created_by_name}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <ShipmentStatusBadge status={s.status} />
          <Flags overdue={s.overdue} />
        </div>
      </header>

      <div className="space-y-4 px-4 py-3">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-slate-400">
              <tr>
                <th className="py-1 pr-3 font-semibold">Item</th>
                <th className="py-1 pr-3 text-right font-semibold">Shipped</th>
                {s.receipt && <th className="py-1 pr-3 text-right font-semibold">Received</th>}
                {s.receipt && <th className="py-1 text-right font-semibold">Accepted</th>}
              </tr>
            </thead>
            <tbody>
              {s.items.map((i) => {
                const r = received.get(i.po_item_id);
                const short = r && r.quantity_received !== i.quantity_shipped;
                const rejected = r && r.quantity_accepted < r.quantity_received;
                return (
                  <tr key={i.po_item_id} className="border-t border-blue-50">
                    <td className="py-1.5 pr-3">
                      {i.item_name}
                      {r && r.item_name_entered.trim().toLowerCase() !== i.item_name.trim().toLowerCase() && (
                        <span className="block text-xs text-amber-700">Entered as "{r.item_name_entered}"</span>
                      )}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {qty(i.quantity_shipped)} {i.unit}
                    </td>
                    {s.receipt && (
                      <td className={`py-1.5 pr-3 text-right tabular-nums ${short ? "font-bold text-brand-red" : ""}`}>{r ? qty(r.quantity_received) : "—"}</td>
                    )}
                    {s.receipt && (
                      <td className={`py-1.5 text-right tabular-nums ${rejected ? "font-bold text-brand-red" : ""}`}>{r ? qty(r.quantity_accepted) : "—"}</td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {s.attachments.length > 0 && (
          <div>
            <p className="mb-1 text-[11px] font-extrabold uppercase tracking-wide text-slate-400">Vendor documents</p>
            <FileList files={s.attachments} />
          </div>
        )}

        {s.receipt && (
          <div className="rounded-lg bg-brand-ice/60 px-3 py-2 text-sm">
            <p className="text-slate-700">
              Received {fmtDateTime(s.receipt.received_at)}
              {s.receipt.received_by_name && ` by ${s.receipt.received_by_name}`}
            </p>
            {s.receipt.notes && <p className="mt-1 whitespace-pre-line text-slate-600">{s.receipt.notes}</p>}
            {s.receipt.attachments.length > 0 && (
              <div className="mt-2">
                <FileList files={s.receipt.attachments} />
              </div>
            )}
          </div>
        )}

        {s.discrepancies.map((d) => (
          <div key={d.id} className={`rounded-lg border px-3 py-2 text-sm ${d.status === "OPEN" ? "border-red-200 bg-red-50/60" : "border-slate-200 bg-slate-50"}`}>
            <div className="flex flex-wrap items-center gap-2">
              <DiscrepancyBadge type={d.type} status={d.status} />
              {d.item_name && <span className="font-semibold text-slate-700">{d.item_name}</span>}
              <span className="text-xs text-slate-500">
                {fmtDateTime(d.created_at)}
                {d.reported_by_name && ` · ${d.reported_by_name}`}
              </span>
            </div>
            {d.description && <p className="mt-1 whitespace-pre-line text-slate-700">{d.description}</p>}
            {d.attachments.length > 0 && (
              <div className="mt-2">
                <FileList files={d.attachments} />
              </div>
            )}
            {d.resolution_note && (
              <p className="mt-2 text-slate-600">
                <strong>Resolution:</strong> {d.resolution_note}
                {d.resolved_by_name && ` (${d.resolved_by_name})`}
              </p>
            )}
          </div>
        ))}

        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </article>
  );
}
