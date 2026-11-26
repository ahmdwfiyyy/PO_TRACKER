import { useState } from "react";
import type { FormEvent } from "react";
import { errorText, sendJson, uploadFiles } from "../api/client";
import { qty, today } from "../api/format";
import type { Discrepancy, DiscrepancyType, PODetail, Shipment } from "../api/types";
import { FilePicker } from "./Attachments";
import { DISCREPANCY_TYPES } from "./StatusBadge";
import { Banner, Field, Modal, Select, Spinner, button, inputCls, redBtn, textareaCls } from "./ui";

function Buttons({ busy, label, onClose }: { busy: boolean; label: string; onClose: () => void }) {
  return (
    <div className="flex justify-end gap-3 pt-2">
      <button type="button" className={button("secondary", "lg")} onClick={onClose}>
        Cancel
      </button>
      <button type="submit" disabled={busy} className={redBtn}>
        {busy && <Spinner />}
        {label}
      </button>
    </div>
  );
}

const leftToShip = (i: PODetail["items"][number]) => Math.max(0, i.quantity_ordered - i.quantity_accepted - i.quantity_in_transit);

// ---------------------------------------------------------------------------
/** Vendor confirms item names and quantities; the PO moves to Preparing. */
export function AcknowledgeModal({ po, onClose, onDone }: { po: PODetail; onClose: () => void; onDone: (po: PODetail) => void }) {
  const [lines, setLines] = useState(() => po.items.map((i) => ({ id: i.id, name: i.item_name, qty: String(i.quantity_ordered) })));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const changed = lines.filter((l, n) => l.name.trim() !== po.items[n].item_name || Number(l.qty) !== po.items[n].quantity_ordered).length;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const items = lines.map((l) => ({ po_item_id: l.id, confirmed_name: l.name.trim(), confirmed_qty: Number(l.qty) }));
      onDone(await sendJson<PODetail>(`/api/pos/${po.id}/acknowledge`, { items, note: note || null }));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Acknowledge ${po.po_number}`} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-5">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <p className="text-sm text-slate-600">
          Check each item and quantity. If something is different (e.g. you can only supply part of it), change it here: Carsem
          Purchasing will be told and will update the PO if they agree.
        </p>
        <div className="space-y-3">
          {lines.map((l, n) => {
            const item = po.items[n];
            const differs = l.name.trim() !== item.item_name || Number(l.qty) !== item.quantity_ordered;
            return (
              <div key={l.id} className={`grid gap-3 rounded-xl border p-3 sm:grid-cols-[minmax(0,3fr)_minmax(0,1fr)] ${differs ? "border-amber-300 bg-amber-50/60" : "border-blue-100"}`}>
                <Field label={`#${item.line_no} Item name`} hint={differs ? `Ordered: ${item.item_name}, ${qty(item.quantity_ordered)} ${item.unit}` : undefined}>
                  <input required maxLength={300} value={l.name} onChange={(e) => setLines((ls) => ls.map((x) => (x.id === l.id ? { ...x, name: e.target.value } : x)))} className={inputCls} />
                </Field>
                <Field label={`Quantity (${item.unit})`}>
                  <input type="number" required min="0.001" step="any" value={l.qty} onChange={(e) => setLines((ls) => ls.map((x) => (x.id === l.id ? { ...x, qty: e.target.value } : x)))} className={inputCls} />
                </Field>
              </div>
            );
          })}
        </div>
        <Field label="Note to Carsem" hint="Optional">
          <textarea maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} className={textareaCls} />
        </Field>
        <Buttons busy={busy} label={changed ? `Acknowledge with ${changed} change${changed > 1 ? "s" : ""}` : "Acknowledge & start preparing"} onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
const COURIERS = ["DHL", "FedEx", "UPS", "J&T Express", "Pos Laju", "GDEX", "City-Link", "Own transport"];

/** Vendor dispatches all or part of what is left to ship. */
export function DispatchModal({ po, onClose, onDone }: { po: PODetail; onClose: () => void; onDone: (po: PODetail, uploadErrors: string[]) => void }) {
  const shippable = po.items.filter((i) => leftToShip(i) > 0);
  const [partial, setPartial] = useState(false);
  const [amounts, setAmounts] = useState<Record<number, string>>(() => Object.fromEntries(shippable.map((i) => [i.id, String(leftToShip(i))])));
  const [courier, setCourier] = useState("");
  const [tracking, setTracking] = useState("");
  const [expected, setExpected] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const setFull = () => {
    setPartial(false);
    setAmounts(Object.fromEntries(shippable.map((i) => [i.id, String(leftToShip(i))])));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const items = shippable
      .map((i) => ({ po_item_id: i.id, quantity: Number(amounts[i.id] || 0) }))
      .filter((i) => i.quantity > 0);
    if (items.length === 0) {
      setError("Enter a quantity for at least one item.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const updated = await sendJson<PODetail>(`/api/pos/${po.id}/shipments`, {
        courier,
        tracking_number: tracking || null,
        expected_delivery_date: expected,
        items,
      });
      const created = updated.shipments[updated.shipments.length - 1];
      const uploadErrors = files.length ? await uploadFiles("shipment", created.id, files) : [];
      onDone(updated, uploadErrors);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Dispatch goods for ${po.po_number}`} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-5">
        <Banner notice={error ? { type: "error", text: error } : null} />

        <div className="inline-flex rounded-xl border border-blue-100 bg-brand-ice p-1" role="radiogroup" aria-label="Delivery type">
          {[
            [false, "Full delivery"],
            [true, "Partial delivery"],
          ].map(([value, label]) => (
            <button
              key={String(value)}
              type="button"
              role="radio"
              aria-checked={partial === value}
              onClick={() => (value ? setPartial(true) : setFull())}
              className={`rounded-lg px-4 py-2 text-sm font-bold transition ${partial === value ? "bg-white text-brand-navy shadow-sm" : "text-slate-500 hover:text-brand-navy"}`}
            >
              {label as string}
            </button>
          ))}
        </div>

        <div className="overflow-x-auto rounded-xl border border-blue-100">
          <table className="w-full min-w-[480px] text-left text-sm">
            <thead className="bg-brand-ice text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2 font-semibold">Item</th>
                <th className="px-3 py-2 text-right font-semibold">Left to ship</th>
                <th className="px-3 py-2 font-semibold">Shipping now</th>
              </tr>
            </thead>
            <tbody>
              {shippable.map((i) => (
                <tr key={i.id} className="border-t border-blue-50">
                  <td className="px-3 py-2">
                    <span className="text-slate-400">#{i.line_no}</span> {i.vendor_confirmed_name ?? i.item_name}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {qty(leftToShip(i))} {i.unit}
                  </td>
                  <td className="w-40 px-3 py-2">
                    <input
                      type="number"
                      min="0"
                      max={leftToShip(i)}
                      step="any"
                      disabled={!partial}
                      aria-label={`Quantity of ${i.item_name}`}
                      value={amounts[i.id] ?? ""}
                      onChange={(e) => setAmounts({ ...amounts, [i.id]: e.target.value })}
                      className={inputCls}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!partial && <p className="-mt-2 text-xs text-slate-500">Everything left to ship is included. Choose "Partial delivery" to send less.</p>}

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Courier">
            <input required maxLength={100} list="couriers" value={courier} onChange={(e) => setCourier(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Tracking number">
            <input maxLength={100} value={tracking} onChange={(e) => setTracking(e.target.value)} className={inputCls} placeholder="Optional" />
          </Field>
          <Field label="Expected delivery">
            <input type="date" required min={today()} value={expected} onChange={(e) => setExpected(e.target.value)} className={inputCls} />
          </Field>
        </div>
        <datalist id="couriers">
          {COURIERS.map((c) => (
            <option key={c} value={c} />
          ))}
        </datalist>

        <Field label="Delivery order / invoice">
          <FilePicker files={files} onChange={setFiles} label="Attach DO or invoice" />
        </Field>

        <Buttons busy={busy} label={partial ? "Dispatch partial delivery" : "Dispatch"} onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
/** Purchasing records how a discrepancy was settled. */
export function ResolveModal({ discrepancy, onClose, onDone }: { discrepancy: Discrepancy; onClose: () => void; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await sendJson(`/api/discrepancies/${discrepancy.id}/resolve`, { resolution_note: note });
      onDone();
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Resolve discrepancy" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <div className="rounded-xl bg-red-50/70 px-4 py-3 text-sm text-slate-700">
          <p className="font-bold text-brand-red">
            {DISCREPANCY_TYPES[discrepancy.type].split(" (")[0]}
            {discrepancy.item_name && ` · ${discrepancy.item_name}`}
          </p>
          {discrepancy.description && <p className="mt-1 whitespace-pre-line">{discrepancy.description}</p>}
        </div>
        <Field label="Resolution" hint="Shown to the vendor, e.g. “Vendor will send 2 replacements” or “Credit note issued”">
          <textarea required maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} className={textareaCls} />
        </Field>
        <p className="text-xs text-slate-500">
          Quantities are not changed: anything short or damaged stays outstanding, so the vendor can ship a replacement as a new
          shipment.
        </p>
        <Buttons busy={busy} label="Mark resolved" onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
/** Report a problem on a shipment that was already received (e.g. damage found after unpacking). */
export function ReportProblemModal({ shipment, onClose, onDone }: { shipment: Shipment; onClose: () => void; onDone: (uploadErrors: string[]) => void }) {
  const [type, setType] = useState<DiscrepancyType>("DAMAGED");
  const [itemId, setItemId] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await sendJson<Shipment>(`/api/shipments/${shipment.id}/discrepancies`, {
        type,
        po_item_id: itemId ? Number(itemId) : null,
        description,
      });
      const created = updated.discrepancies[updated.discrepancies.length - 1];
      onDone(files.length ? await uploadFiles("discrepancy", created.id, files) : []);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Report a problem with ${shipment.shipment_no}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <Field label="Problem">
          <Select value={type} onChange={(e) => setType(e.target.value as DiscrepancyType)}>
            {Object.entries(DISCREPANCY_TYPES).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Item">
          <Select value={itemId} onChange={(e) => setItemId(e.target.value)}>
            <option value="">Whole shipment</option>
            {shipment.items.map((i) => (
              <option key={i.po_item_id} value={i.po_item_id}>
                {i.item_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="What happened">
          <textarea required maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} className={textareaCls} />
        </Field>
        <Field label="Photos">
          <FilePicker files={files} onChange={setFiles} label="Add photos" />
        </Field>
        <Buttons busy={busy} label="Report problem" onClose={onClose} />
      </form>
    </Modal>
  );
}
