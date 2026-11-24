import { useCallback, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, errorText, sendJson } from "../api/client";
import { fmtDate, fmtDateTime, qty } from "../api/format";
import type { PODetail, POItem } from "../api/types";
import { Flags, POStatusBadge, ShipmentStatusBadge, statusLabel } from "../components/StatusBadge";
import {
  BackIcon,
  Badge,
  Banner,
  Card,
  EditIcon,
  EmptyState,
  Field,
  Loading,
  Modal,
  Spinner,
  TruckIcon,
  redBtn,
  secondaryBtn,
  tableHead,
  td,
  textareaCls,
  th,
} from "../components/ui";
import type { Notice } from "../components/ui";
import { useUser } from "../context/AuthContext";

function Info({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-extrabold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-slate-800">{children}</dd>
    </div>
  );
}

function Progress({ item }: { item: POItem }) {
  const accepted = Math.min(100, (item.quantity_accepted / item.quantity_ordered) * 100);
  const transit = Math.min(100 - accepted, (item.quantity_in_transit / item.quantity_ordered) * 100);
  return (
    <div className="flex h-2 w-28 overflow-hidden rounded-full bg-slate-100" title={`${Math.round(accepted)}% accepted`}>
      <div className="bg-emerald-500" style={{ width: `${accepted}%` }} />
      <div className="bg-brand-bright/60" style={{ width: `${transit}%` }} />
    </div>
  );
}

function CancelModal({ po, onClose, onDone }: { po: PODetail; onClose: () => void; onDone: (po: PODetail) => void }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      onDone(await sendJson<PODetail>(`/api/pos/${po.id}/cancel`, { reason: reason || null }));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Cancel ${po.po_number}?`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <p className="text-sm text-slate-600">
          The vendor will see this PO as cancelled. This cannot be undone, but the PO and its history are kept.
        </p>
        <Field label="Reason" hint="Shown in the PO timeline">
          <textarea maxLength={2000} value={reason} onChange={(e) => setReason(e.target.value)} className={textareaCls} />
        </Field>
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" className={`${secondaryBtn} h-12`} onClick={onClose}>
            Keep PO
          </button>
          <button type="submit" disabled={busy} className={redBtn}>
            {busy && <Spinner />}
            Cancel PO
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default function PoDetailPage() {
  const { id } = useParams();
  const user = useUser();
  const location = useLocation();
  const [po, setPo] = useState<PODetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<Notice>(() => {
    const text = (location.state as { notice?: string } | null)?.notice;
    return text ? { type: "success", text } : null;
  });
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(() => {
    api<PODetail>(`/api/pos/${id}`)
      .then(setPo)
      .catch((err) => setError(errorText(err)));
  }, [id]);
  useEffect(load, [load]);

  const backTo = (
    <Link to="/pos" className={secondaryBtn}>
      <BackIcon />
      All POs
    </Link>
  );

  if (error) {
    return (
      <Card title="Purchase order" actions={backTo}>
        <EmptyState title={error} text="It may have been removed, or you may not have access to it." />
      </Card>
    );
  }
  if (!po) return <Loading />;

  const isPurchasing = user.role === "purchasing";
  const closed = po.status === "DELIVERED" || po.status === "CANCELLED";
  const showConfirmed = po.items.some((i) => i.vendor_confirmed_name !== null || i.vendor_confirmed_qty !== null);

  return (
    <div className="space-y-7">
      <Card
        eyebrow={po.vendor.name}
        title={
          <span className="flex flex-wrap items-center gap-3">
            {po.po_number}
            <span className="flex flex-wrap gap-1.5">
              <POStatusBadge status={po.status} />
              <Flags overdue={po.overdue} discrepancy={po.has_open_discrepancy} />
            </span>
          </span>
        }
        description={`Created ${fmtDateTime(po.created_at)}${po.created_by_name ? ` by ${po.created_by_name}` : ""}`}
        actions={
          <>
            {backTo}
            {isPurchasing && !closed && (
              <>
                <Link to={`/pos/${po.id}/edit`} className={secondaryBtn}>
                  <EditIcon className="h-4 w-4" />
                  Edit
                </Link>
                <button type="button" className={`${secondaryBtn} text-brand-red`} onClick={() => setCancelling(true)}>
                  Cancel PO
                </button>
              </>
            )}
          </>
        }
      >
        <Banner notice={notice} />
        <dl className="grid grid-cols-2 gap-5 md:grid-cols-4">
          <Info label="Issue date">{fmtDate(po.issue_date)}</Info>
          <Info label="Required by">
            <span className={po.overdue ? "text-brand-red" : ""}>{fmtDate(po.required_date)}</span>
          </Info>
          <Info label="Vendor acknowledged">{po.acknowledged_at ? fmtDateTime(po.acknowledged_at) : "Not yet"}</Info>
          <Info label="ERP reference">{po.external_ref ?? "—"}</Info>
        </dl>
        {po.notes && (
          <div className="mt-5 whitespace-pre-line rounded-xl border border-blue-100 bg-brand-ice/50 px-4 py-3 text-sm text-slate-700">{po.notes}</div>
        )}
      </Card>

      <Card title="Line items" description="Accepted quantities count toward the PO. Damaged or short quantities stay outstanding." bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left text-sm">
            <thead className={tableHead}>
              <tr>
                <th className={th}>#</th>
                <th className={th}>Item</th>
                <th className={`${th} text-right`}>Ordered</th>
                {showConfirmed && <th className={th}>Vendor confirmed</th>}
                <th className={`${th} text-right`}>Shipped</th>
                <th className={`${th} text-right`}>Accepted</th>
                <th className={`${th} text-right`}>Outstanding</th>
                <th className={th}>Progress</th>
              </tr>
            </thead>
            <tbody>
              {po.items.map((item) => {
                const nameDiffers = item.vendor_confirmed_name !== null && item.vendor_confirmed_name !== item.item_name;
                const qtyDiffers = item.vendor_confirmed_qty !== null && item.vendor_confirmed_qty !== item.quantity_ordered;
                return (
                  <tr key={item.id} className="border-t border-blue-50">
                    <td className={`${td} text-slate-400`}>{item.line_no}</td>
                    <td className={td}>
                      <p className="font-semibold text-slate-800">{item.item_name}</p>
                      {item.item_code && <p className="text-xs text-slate-400">{item.item_code}</p>}
                    </td>
                    <td className={`${td} whitespace-nowrap text-right tabular-nums`}>
                      {qty(item.quantity_ordered)} {item.unit}
                    </td>
                    {showConfirmed && (
                      <td className={td}>
                        {nameDiffers || qtyDiffers ? (
                          <span className="flex flex-col gap-1">
                            <Badge tone="amber">Differs</Badge>
                            <span className="text-xs text-slate-600">
                              {item.vendor_confirmed_name ?? item.item_name} · {qty(item.vendor_confirmed_qty ?? item.quantity_ordered)} {item.unit}
                            </span>
                          </span>
                        ) : (
                          <Badge tone="green">Matches</Badge>
                        )}
                      </td>
                    )}
                    <td className={`${td} text-right tabular-nums`}>{qty(item.quantity_shipped)}</td>
                    <td className={`${td} text-right tabular-nums`}>{qty(item.quantity_accepted)}</td>
                    <td className={`${td} text-right font-bold tabular-nums ${item.quantity_outstanding > 0 ? "text-brand-navy" : "text-emerald-600"}`}>
                      {qty(item.quantity_outstanding)}
                    </td>
                    <td className={td}>
                      <Progress item={item} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-7 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card title="Shipments" description="Each dispatch from the vendor, full or partial.">
          {po.shipments.length === 0 ? (
            <EmptyState title="No shipments yet" text="Shipments appear here when the vendor dispatches goods." />
          ) : (
            <ul className="space-y-3">
              {po.shipments.map((s) => (
                <li key={s.id} className="rounded-xl border border-blue-100 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="flex items-center gap-2 font-bold text-brand-navy">
                      <TruckIcon className="h-5 w-5 text-brand-blue" />
                      {s.shipment_no}
                      {s.is_partial && <Badge tone="violet">Partial</Badge>}
                    </p>
                    <span className="flex gap-1.5">
                      <ShipmentStatusBadge status={s.status} />
                      <Flags overdue={s.overdue} />
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">
                    {s.courier ?? "Courier not given"}
                    {s.tracking_number && ` · ${s.tracking_number}`} · expected {fmtDate(s.expected_delivery_date)}
                  </p>
                  <ul className="mt-2 text-sm text-slate-700">
                    {s.items.map((i) => (
                      <li key={i.po_item_id}>
                        {i.item_name}: <strong>{qty(i.quantity_shipped)}</strong> {i.unit}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Timeline" description="Every status change, newest last.">
          <ol className="relative space-y-5 border-l-2 border-blue-100 pl-5">
            {po.history.map((h) => (
              <li key={h.id} className="relative">
                <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full border-2 border-white bg-brand-blue ring-2 ring-blue-100" />
                <p className="text-sm font-bold text-slate-800">
                  {h.entity_type === "shipment" ? "Shipment " : ""}
                  {h.old_status ? `${statusLabel(h.old_status)} → ${statusLabel(h.new_status)}` : statusLabel(h.new_status)}
                </p>
                <p className="text-xs text-slate-500">
                  {fmtDateTime(h.changed_at)}
                  {h.changed_by_name && ` · ${h.changed_by_name}`}
                </p>
                {h.note && <p className="mt-1 text-sm text-slate-600">{h.note}</p>}
              </li>
            ))}
          </ol>
        </Card>
      </div>

      {cancelling && (
        <CancelModal
          po={po}
          onClose={() => setCancelling(false)}
          onDone={(updated) => {
            setPo(updated);
            setCancelling(false);
            setNotice({ type: "success", text: "PO cancelled." });
          }}
        />
      )}
    </div>
  );
}
