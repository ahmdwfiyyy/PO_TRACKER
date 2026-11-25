import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText, sendJson } from "../api/client";
import { today } from "../api/format";
import type { PODetail, POItemInput, Vendor } from "../api/types";
import {
  BackIcon,
  Banner,
  Card,
  Field,
  Loading,
  PlusIcon,
  Select,
  Spinner,
  TrashIcon,
  button,
  inputCls,
  redBtn,
  secondaryBtn,
  smallBtn,
  textareaCls,
} from "../components/ui";

type Line = { key: number; item_name: string; item_code: string; quantity: string; unit: string };

let nextKey = 1;
const blankLine = (): Line => ({ key: nextKey++, item_name: "", item_code: "", quantity: "", unit: "pcs" });

const UNITS = ["pcs", "pair", "box", "pack", "roll", "set", "kg", "g", "l", "m", "bottle", "unit"];

/** Create a PO, or edit one (/pos/:id/edit). */
export default function PoFormPage() {
  const { id } = useParams();
  const editing = id !== undefined;
  const navigate = useNavigate();

  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [po, setPo] = useState<PODetail | null>(null);
  const [poNumber, setPoNumber] = useState("");
  const [vendorId, setVendorId] = useState("");
  const [issueDate, setIssueDate] = useState(today());
  const [requiredDate, setRequiredDate] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([blankLine()]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Vendor[]>("/api/vendors")
      .then(setVendors)
      .catch((err) => setError(errorText(err)));
    if (!editing) return;
    api<PODetail>(`/api/pos/${id}`)
      .then((data) => {
        setPo(data);
        setPoNumber(data.po_number);
        setVendorId(String(data.vendor.id));
        setIssueDate(data.issue_date);
        setRequiredDate(data.required_date ?? "");
        setNotes(data.notes ?? "");
        setLines(
          data.items.map((i) => ({
            key: nextKey++,
            item_name: i.item_name,
            item_code: i.item_code ?? "",
            quantity: String(i.quantity_ordered),
            unit: i.unit,
          })),
        );
      })
      .catch((err) => setError(errorText(err)));
  }, [editing, id]);

  const locked = po?.locked ?? false;
  const closed = po?.status === "DELIVERED" || po?.status === "CANCELLED";

  const updateLine = (key: number, patch: Partial<Line>) =>
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    const items: POItemInput[] = lines.map((l) => ({
      item_name: l.item_name.trim(),
      item_code: l.item_code.trim() || null,
      quantity_ordered: Number(l.quantity),
      unit: l.unit.trim(),
    }));
    if (!locked && items.some((i) => !(i.quantity_ordered > 0))) {
      setError("Every line needs a quantity above zero.");
      return;
    }
    setBusy(true);
    try {
      const result = editing
        ? await sendJson<PODetail>(
            `/api/pos/${id}`,
            locked
              ? { notes: notes || null, required_date: requiredDate || null }
              : {
                  po_number: poNumber,
                  vendor_id: Number(vendorId),
                  issue_date: issueDate,
                  required_date: requiredDate || null,
                  notes: notes || null,
                  items,
                },
            "PUT",
          )
        : await sendJson<PODetail>("/api/pos", {
            po_number: poNumber,
            vendor_id: Number(vendorId),
            issue_date: issueDate,
            required_date: requiredDate || null,
            notes: notes || null,
            items,
          });
      navigate(`/pos/${result.id}`, { state: { notice: editing ? "PO updated." : "PO created." } });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  if (!vendors || (editing && !po && !error)) return <Loading />;

  return (
    <Card
      eyebrow="Purchasing"
      title={editing ? `Edit ${po?.po_number ?? "PO"}` : "New purchase order"}
      description={editing ? "Change the PO details or line items." : "The vendor will see this PO as soon as you save it."}
      actions={
        <Link to={editing ? `/pos/${id}` : "/pos"} className={secondaryBtn}>
          <BackIcon />
          Back
        </Link>
      }
    >
      <form onSubmit={submit} className="space-y-7">
        <Banner notice={error ? { type: "error", text: error } : null} />
        {locked && !closed && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            The vendor has already acknowledged this PO, so only the <strong>required date</strong> and <strong>notes</strong> can be changed.
          </div>
        )}
        {vendors.length === 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            There are no vendors yet. <Link to="/admin" className="font-bold underline">Add a vendor</Link> first.
          </div>
        )}

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="PO number">
            <input required maxLength={50} disabled={locked} value={poNumber} onChange={(e) => setPoNumber(e.target.value)} className={inputCls} placeholder="e.g. PO-2026-0101" />
          </Field>
          <Field label="Vendor">
            <Select required disabled={locked} value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
              <option value="">Choose a vendor</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Issue date">
            <input type="date" required disabled={locked} value={issueDate} onChange={(e) => setIssueDate(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Required by" hint="The PO shows as overdue after this date">
            <input type="date" min={issueDate} value={requiredDate} onChange={(e) => setRequiredDate(e.target.value)} className={inputCls} />
          </Field>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-extrabold uppercase tracking-wide text-brand-navy">Line items</h3>
            {!locked && (
              <button type="button" className={smallBtn} onClick={() => setLines((ls) => [...ls, blankLine()])}>
                <PlusIcon className="h-4 w-4" />
                Add line
              </button>
            )}
          </div>
          <div className="space-y-3">
            {lines.map((line, index) => (
              <div key={line.key} className="grid grid-cols-2 gap-3 rounded-xl border border-blue-100 bg-brand-ice/30 p-3 md:grid-cols-[2.5rem_minmax(0,3fr)_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)_2.5rem] md:items-end">
                <span className="col-span-2 text-xs font-extrabold text-slate-400 md:col-span-1 md:pb-3.5 md:text-center">#{index + 1}</span>
                <Field label="Item name">
                  <input required maxLength={300} disabled={locked} value={line.item_name} onChange={(e) => updateLine(line.key, { item_name: e.target.value })} className={inputCls} />
                </Field>
                <Field label="Item code">
                  <input maxLength={100} disabled={locked} value={line.item_code} onChange={(e) => updateLine(line.key, { item_code: e.target.value })} className={inputCls} placeholder="Optional" />
                </Field>
                <Field label="Quantity">
                  <input type="number" required min="0.001" step="any" disabled={locked} value={line.quantity} onChange={(e) => updateLine(line.key, { quantity: e.target.value })} className={inputCls} />
                </Field>
                <Field label="Unit">
                  <input required maxLength={20} list="units" disabled={locked} value={line.unit} onChange={(e) => updateLine(line.key, { unit: e.target.value })} className={inputCls} />
                </Field>
                {!locked && (
                  <button
                    type="button"
                    aria-label={`Remove line ${index + 1}`}
                    disabled={lines.length === 1}
                    onClick={() => setLines((ls) => ls.filter((l) => l.key !== line.key))}
                    className="grid h-12 w-full place-items-center rounded-xl text-slate-400 transition hover:bg-red-50 hover:text-brand-red disabled:opacity-30 md:w-10"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                )}
              </div>
            ))}
          </div>
          <datalist id="units">
            {UNITS.map((u) => (
              <option key={u} value={u} />
            ))}
          </datalist>
        </div>

        <Field label="Notes" hint="Visible to the vendor">
          <textarea maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} className={textareaCls} />
        </Field>

        <div className="flex justify-end gap-3 border-t border-blue-50 pt-5">
          <Link to={editing ? `/pos/${id}` : "/pos"} className={button("secondary", "lg")}>
            Cancel
          </Link>
          <button type="submit" disabled={busy || closed} className={redBtn}>
            {busy && <Spinner />}
            {editing ? "Save changes" : "Create PO"}
          </button>
        </div>
      </form>
    </Card>
  );
}
