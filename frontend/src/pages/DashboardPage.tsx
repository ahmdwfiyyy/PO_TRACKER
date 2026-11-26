import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api/client";
import { fmtDate, fmtDateTime } from "../api/format";
import type { DashboardSummary, DiscrepancyListItem, POStatus } from "../api/types";
import DiscrepancyItem from "../components/DiscrepancyItem";
import { ResolveModal } from "../components/PoActions";
import { POStatusBadge, PO_STATUS_OPTIONS, statusLabel } from "../components/StatusBadge";
import { AlertIcon, Banner, Card, ClipboardIcon, ClockIcon, EmptyState, Loading, TruckIcon, panel, smallBtn } from "../components/ui";
import type { Notice } from "../components/ui";

/** Headline number. The value is plain ink; an icon + label says what it is (never colour alone). */
function Tile({ to, label, value, icon, attention = false }: { to: string; label: string; value: number; icon: ReactNode; attention?: boolean }) {
  const alert = attention && value > 0;
  return (
    <Link
      to={to}
      className={`${panel} group flex items-center justify-between gap-3 p-5 transition hover:-translate-y-0.5 hover:border-brand-blue`}
    >
      <div>
        <p className="text-[11px] font-extrabold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-1 text-3xl font-extrabold tabular-nums tracking-tight text-brand-navy">{value}</p>
      </div>
      <span className={`grid h-11 w-11 place-items-center rounded-xl ${alert ? "bg-red-50 text-brand-red" : "bg-brand-ice text-brand-blue"}`}>{icon}</span>
    </Link>
  );
}

/** Purchasing's start page: what needs attention right now. */
export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [resolving, setResolving] = useState<DiscrepancyListItem | null>(null);

  const load = useCallback(() => {
    api<DashboardSummary>("/api/dashboard/summary")
      .then(setData)
      .catch((err) => setNotice({ type: "error", text: errorText(err) }));
  }, []);
  useEffect(load, [load]);

  if (!data) return notice ? <Banner notice={notice} /> : <Loading />;

  const lateCount = data.overdue.length + data.overdue_shipments.length;

  return (
    <div className="space-y-7">
      <Banner notice={notice} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tile to="/pos?state=open" label="Open POs" value={data.open_pos} icon={<ClipboardIcon />} />
        <Tile to="/pos?overdue=true" label="Overdue POs" value={data.overdue_pos} icon={<ClockIcon />} attention />
        <Tile to="/pos?status=ON_THE_WAY" label="Shipments on the way" value={data.in_transit} icon={<TruckIcon />} />
        <Tile to="/discrepancies" label="Open discrepancies" value={data.open_discrepancies} icon={<AlertIcon />} attention />
      </div>

      <Card title="POs by status" description="Click a status to see those POs.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {PO_STATUS_OPTIONS.map(({ value }) => (
            <Link
              key={value}
              to={`/pos?status=${value}`}
              className="flex flex-col items-start gap-2 rounded-xl border border-blue-100 p-4 transition hover:border-brand-blue hover:bg-brand-ice/60"
            >
              <POStatusBadge status={value as POStatus} />
              <span className="text-2xl font-extrabold tabular-nums text-brand-navy">{data.status_counts[value as POStatus] ?? 0}</span>
            </Link>
          ))}
        </div>
      </Card>

      <div className="grid gap-7 lg:grid-cols-2">
        <Card
          title="Overdue"
          description="POs past their required date, and shipments past their expected delivery."
          actions={
            data.overdue_pos > data.overdue.length && (
              <Link to="/pos?overdue=true" className={smallBtn}>
                See all
              </Link>
            )
          }
        >
          {lateCount === 0 ? (
            <EmptyState title="Nothing overdue" />
          ) : (
            <ul className="divide-y divide-blue-50">
              {data.overdue.map((o) => (
                <li key={`po-${o.id}`} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="min-w-0">
                    <Link to={`/pos/${o.id}`} className="font-bold text-brand-navy hover:text-brand-red">
                      {o.po_number}
                    </Link>
                    <p className="text-sm text-slate-500">
                      {o.vendor_name} · required {fmtDate(o.required_date)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <POStatusBadge status={o.status} />
                    <span className="text-sm font-bold tabular-nums text-slate-800">{o.days_late}d late</span>
                  </div>
                </li>
              ))}
              {data.overdue_shipments.map((s) => (
                <li key={`s-${s.id}`} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="min-w-0">
                    <Link to={`/pos/${s.po_id}`} className="font-bold text-brand-navy hover:text-brand-red">
                      {s.shipment_no}
                    </Link>
                    <p className="text-sm text-slate-500">
                      {s.vendor_name} · expected {fmtDate(s.expected_delivery_date)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wide text-slate-500">
                      <TruckIcon className="h-3.5 w-3.5" />
                      Not received
                    </span>
                    <span className="text-sm font-bold tabular-nums text-slate-800">{s.days_late}d late</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Open discrepancies"
          description="Newest first."
          actions={
            <Link to="/discrepancies" className={smallBtn}>
              See all
            </Link>
          }
        >
          {data.discrepancies.length === 0 ? (
            <EmptyState title="No open discrepancies" />
          ) : (
            <div className="space-y-3">
              {data.discrepancies.map((d) => (
                <DiscrepancyItem key={d.id} d={d} compact onResolve={() => setResolving(d)} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Recent activity" description="The latest status changes across all POs.">
        {data.activity.length === 0 ? (
          <EmptyState title="No activity yet" />
        ) : (
          <ol className="divide-y divide-blue-50">
            {data.activity.map((a) => (
              <li key={a.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3">
                <p className="text-sm text-slate-700">
                  <Link to={`/pos/${a.po_id}`} className="font-bold text-brand-navy hover:text-brand-red">
                    {a.po_number}
                  </Link>
                  {a.subject !== "PO" && <span className="text-slate-500"> · {a.subject}</span>}
                  {": "}
                  {a.old_status ? `${statusLabel(a.old_status)} → ${statusLabel(a.new_status)}` : statusLabel(a.new_status)}
                  {a.note && <span className="text-slate-500"> · {a.note}</span>}
                </p>
                <p className="text-xs text-slate-400">
                  {fmtDateTime(a.changed_at)}
                  {a.changed_by_name && ` · ${a.changed_by_name}`}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Card>

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
    </div>
  );
}
