import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, errorText, query } from "../api/client";
import { fmtDate } from "../api/format";
import type { Page, POListItem, Vendor } from "../api/types";
import { Flags, POStatusBadge, PO_STATUS_OPTIONS } from "../components/StatusBadge";
import {
  Banner,
  Card,
  EmptyState,
  Loading,
  Pager,
  PlusIcon,
  SearchIcon,
  Select,
  inputCls,
  redBtn,
  tableHead,
  td,
  th,
} from "../components/ui";
import { useUser } from "../context/AuthContext";

// Filters live in the URL, so a filtered list can be bookmarked or shared.
export default function PoListPage() {
  const user = useUser();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Page<POListItem> | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState(params.get("q") ?? "");

  const isPurchasing = user.role === "purchasing";
  const isVendor = user.role === "vendor";
  const filters = {
    q: params.get("q") ?? "",
    status: params.get("status") ?? "",
    vendor_id: params.get("vendor_id") ?? "",
    overdue: params.get("overdue") ?? "",
    has_discrepancy: params.get("has_discrepancy") ?? "",
    state: params.get("state") ?? (isVendor ? "open" : ""),
    page: Number(params.get("page") ?? 1),
  };

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (isPurchasing) api<Vendor[]>("/api/vendors").then(setVendors).catch(() => setVendors([]));
  }, [isPurchasing]);

  const key = params.toString();
  useEffect(() => {
    setData(null);
    setError("");
    api<Page<POListItem>>(`/api/pos${query({ ...filters, page_size: 20 })}`)
      .then(setData)
      .catch((err) => setError(errorText(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Search as you type, with a short pause
  useEffect(() => {
    const t = setTimeout(() => search !== filters.q && setFilter("q", search.trim()), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const title = isVendor ? "My purchase orders" : "Purchase orders";
  const description = isVendor
    ? "Every PO Carsem has issued to you. Delivered and cancelled POs stay under History."
    : user.role === "receiving"
      ? "POs that have shipments on the way or already received."
      : "Search by PO number, vendor or item, and filter by status.";

  return (
    <Card
      eyebrow={isVendor ? user.vendor_name ?? "Vendor" : "Purchasing"}
      title={title}
      description={description}
      actions={
        isPurchasing && (
          <Link to="/pos/new" className={redBtn}>
            <PlusIcon className="h-4 w-4" />
            New PO
          </Link>
        )
      }
    >
      {isVendor && (
        <div className="mb-5 inline-flex rounded-xl border border-blue-100 bg-brand-ice p-1" role="tablist">
          {[
            ["open", "Open"],
            ["closed", "History"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={filters.state === value}
              onClick={() => setFilter("state", value)}
              className={`rounded-lg px-4 py-2 text-sm font-bold transition ${
                filters.state === value ? "bg-white text-brand-navy shadow-sm" : "text-slate-500 hover:text-brand-navy"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="mb-5 grid gap-3 md:grid-cols-[minmax(0,2fr)_repeat(2,minmax(0,1fr))]">
        <label className="relative block">
          <span className="sr-only">Search</span>
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            placeholder="Search PO number, vendor or item"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`${inputCls} pl-11`}
          />
        </label>
        <Select aria-label="Status" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
          <option value="">All statuses</option>
          {PO_STATUS_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </Select>
        {isPurchasing ? (
          <Select aria-label="Vendor" value={filters.vendor_id} onChange={(e) => setFilter("vendor_id", e.target.value)}>
            <option value="">All vendors</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </Select>
        ) : (
          <div className="hidden md:block" />
        )}
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ["overdue", "Overdue only"],
          ["has_discrepancy", "With open discrepancy"],
        ].map(([key, label]) => {
          const on = filters[key as "overdue" | "has_discrepancy"] === "true";
          return (
            <button
              key={key}
              type="button"
              aria-pressed={on}
              onClick={() => setFilter(key, on ? "" : "true")}
              className={`rounded-full border px-4 py-2 text-xs font-bold transition ${
                on ? "border-brand-red bg-red-50 text-brand-red" : "border-blue-100 bg-white text-slate-600 hover:border-brand-blue"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>

      <Banner notice={error ? { type: "error", text: error } : null} />
      {!data && !error && <Loading />}
      {data && data.items.length === 0 && (
        <EmptyState
          title="No purchase orders found"
          text={params.toString() ? "Try clearing the search or filters." : isPurchasing ? "Create the first PO to get started." : undefined}
        />
      )}
      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border border-blue-100">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
              <thead className={tableHead}>
                <tr>
                  <th className={th}>PO number</th>
                  {!isVendor && <th className={th}>Vendor</th>}
                  <th className={th}>Items</th>
                  <th className={th}>Status</th>
                  <th className={th}>Issued</th>
                  <th className={th}>Required by</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((po) => (
                  <tr
                    key={po.id}
                    onClick={() => navigate(`/pos/${po.id}`)}
                    className="cursor-pointer border-t border-blue-50 transition hover:bg-brand-ice/60"
                  >
                    <td className={`${td} font-bold text-brand-navy`}>
                      <Link to={`/pos/${po.id}`} onClick={(e) => e.stopPropagation()} className="hover:text-brand-red">
                        {po.po_number}
                      </Link>
                    </td>
                    {!isVendor && <td className={td}>{po.vendor.name}</td>}
                    <td className={`${td} text-slate-600`}>
                      <span className="line-clamp-1">{po.item_summary}</span>
                    </td>
                    <td className={td}>
                      <div className="flex flex-wrap gap-1.5">
                        <POStatusBadge status={po.status} />
                        <Flags overdue={po.overdue} discrepancy={po.has_open_discrepancy} />
                      </div>
                    </td>
                    <td className={`${td} whitespace-nowrap text-slate-600`}>{fmtDate(po.issue_date)}</td>
                    <td className={`${td} whitespace-nowrap ${po.overdue ? "font-bold text-brand-red" : "text-slate-600"}`}>
                      {fmtDate(po.required_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between pt-4 text-sm text-slate-500">
            <span>
              {data.total} purchase order{data.total === 1 ? "" : "s"}
            </span>
            <Pager page={data.page} pages={data.pages} onPage={(p) => setFilter("page", String(p))} />
          </div>
        </>
      )}
    </Card>
  );
}
