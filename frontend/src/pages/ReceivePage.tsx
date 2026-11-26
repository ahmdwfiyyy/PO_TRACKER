import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText, sendJson, uploadFiles } from "../api/client";
import { fmtDate, qty } from "../api/format";
import type { DiscrepancyType, Shipment, ShipmentItem } from "../api/types";
import { FileList, FilePicker } from "../components/Attachments";
import { DISCREPANCY_TYPES } from "../components/StatusBadge";
import {
  AlertIcon,
  BackIcon,
  Badge,
  Banner,
  Card,
  CheckIcon,
  EmptyState,
  Field,
  Loading,
  Select,
  Spinner,
  button,
  input,
  redBtn,
  secondaryBtn,
  textareaCls,
} from "../components/ui";

type Line = { name: string; received: string; accepted: string; acceptedTouched: boolean };
type Problem = { po_item_id: number | null; type: DiscrepancyType; message: string };

const norm = (s: string | null | undefined) => (s ?? "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");

/** Same rules as the backend (services/shipments.py find_mismatches), so problems show while typing. */
function problemsFor(item: ShipmentItem, line: Line): Problem[] {
  const out: Problem[] = [];
  const received = Number(line.received || 0);
  const accepted = Number(line.accepted || 0);
  const label = `Line ${item.line_no} (${item.item_name})`;
  if (![norm(item.item_name), norm(item.vendor_confirmed_name)].includes(norm(line.name))) {
    out.push({ po_item_id: item.po_item_id, type: "WRONG_ITEM", message: `${label}: received "${line.name}"` });
  }
  if (received < item.quantity_shipped) {
    out.push({ po_item_id: item.po_item_id, type: "SHORT", message: `${label}: ${qty(item.quantity_shipped - received)} ${item.unit} short` });
  } else if (received > item.quantity_shipped) {
    out.push({ po_item_id: item.po_item_id, type: "EXCESS", message: `${label}: ${qty(received - item.quantity_shipped)} ${item.unit} extra` });
  }
  if (accepted < received) {
    out.push({ po_item_id: item.po_item_id, type: "DAMAGED", message: `${label}: ${qty(received - accepted)} ${item.unit} not accepted` });
  }
  return out;
}

/** Receiving keys in what actually arrived. Built for a tablet at the dock: big inputs, live checks. */
export default function ReceivePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [lines, setLines] = useState<Record<number, Line>>({});
  const [notes, setNotes] = useState("");
  const [otherProblem, setOtherProblem] = useState(false);
  const [otherType, setOtherType] = useState<DiscrepancyType>("OTHER");
  const [otherItem, setOtherItem] = useState("");
  const [problemNote, setProblemNote] = useState("");
  const [problemPhotos, setProblemPhotos] = useState<File[]>([]);
  const [deliveryPhotos, setDeliveryPhotos] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Shipment>(`/api/shipments/${id}`)
      .then((s) => {
        setShipment(s);
        setLines(
          Object.fromEntries(
            s.items.map((i) => [i.po_item_id, { name: i.item_name, received: String(i.quantity_shipped), accepted: String(i.quantity_shipped), acceptedTouched: false }]),
          ),
        );
      })
      .catch((err) => setError(errorText(err)));
  }, [id]);

  const detected = useMemo(
    () => (shipment ? shipment.items.flatMap((i) => (lines[i.po_item_id] ? problemsFor(i, lines[i.po_item_id]) : [])) : []),
    [shipment, lines],
  );
  const declaring = detected.length > 0 || otherProblem;

  const update = (itemId: number, patch: Partial<Line>) =>
    setLines((ls) => {
      const next = { ...ls[itemId], ...patch };
      // Accepted follows received until someone changes it by hand
      if ("received" in patch && !next.acceptedTouched) next.accepted = patch.received ?? next.accepted;
      return { ...ls, [itemId]: next };
    });

  if (error && !shipment) {
    return (
      <Card title="Receive shipment">
        <EmptyState title={error} text="It may not exist, or you may not have access to it." />
      </Card>
    );
  }
  if (!shipment) return <Loading />;

  const back = (
    <Link to="/incoming" className={secondaryBtn}>
      <BackIcon />
      Incoming
    </Link>
  );

  if (shipment.status !== "ON_THE_WAY") {
    return (
      <Card title={`Receive ${shipment.shipment_no}`} actions={back}>
        <EmptyState title="This shipment has already been received" text="Open the PO to see what was recorded." action={<Link to={`/pos/${shipment.po_id}`} className={redBtn}>Open {shipment.po_number}</Link>} />
      </Card>
    );
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (declaring && !problemNote.trim()) {
      setError("Describe the problem so Purchasing can follow it up.");
      return;
    }
    const discrepancies = [
      ...detected.map((p) => ({ po_item_id: p.po_item_id, type: p.type, description: `${p.message}\n${problemNote.trim()}` })),
      ...(otherProblem ? [{ po_item_id: otherItem ? Number(otherItem) : null, type: otherType, description: problemNote.trim() }] : []),
    ];
    setBusy(true);
    try {
      const result = await sendJson<Shipment>(`/api/shipments/${shipment.id}/receive`, {
        items: shipment.items.map((i) => ({
          po_item_id: i.po_item_id,
          item_name_entered: lines[i.po_item_id].name.trim(),
          quantity_received: Number(lines[i.po_item_id].received || 0),
          quantity_accepted: Number(lines[i.po_item_id].accepted || 0),
        })),
        notes: notes.trim() || null,
        discrepancies,
      });
      const errors = [
        ...(result.receipt && deliveryPhotos.length ? await uploadFiles("receipt", result.receipt.id, deliveryPhotos) : []),
        ...(result.discrepancies.length && problemPhotos.length ? await uploadFiles("discrepancy", result.discrepancies[0].id, problemPhotos) : []),
      ];
      const text = discrepancies.length
        ? `${shipment.shipment_no} received with a discrepancy. Purchasing has been alerted.`
        : `${shipment.shipment_no} received and marked delivered.`;
      navigate("/incoming", { state: { notice: errors.length ? `${text} Some photos failed to upload: ${errors.join(" ")}` : text } });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <Card
      eyebrow={`${shipment.po_number} · ${shipment.vendor.name}`}
      title={`Receive ${shipment.shipment_no}`}
      description={`${shipment.courier ?? "Courier not given"}${shipment.tracking_number ? ` · ${shipment.tracking_number}` : ""} · expected ${fmtDate(shipment.expected_delivery_date)}`}
      actions={back}
    >
      <form onSubmit={submit} className="space-y-7">
        <Banner notice={error ? { type: "error", text: error } : null} />

        {shipment.attachments.length > 0 && (
          <div>
            <p className="mb-2 text-sm font-semibold text-slate-700">Vendor documents (DO / invoice)</p>
            <FileList files={shipment.attachments} />
          </div>
        )}

        <div className="space-y-4">
          {shipment.items.map((item) => {
            const line = lines[item.po_item_id];
            const problems = problemsFor(item, line);
            return (
              <fieldset
                key={item.po_item_id}
                className={`rounded-2xl border-2 p-4 transition ${problems.length ? "border-red-300 bg-red-50/40" : "border-emerald-200 bg-emerald-50/30"}`}
              >
                <legend className="flex flex-wrap items-center gap-2 px-1 text-sm font-extrabold text-brand-navy">
                  Line {item.line_no}
                  {problems.length ? <Badge tone="red">Check</Badge> : <Badge tone="green">Matches</Badge>}
                </legend>
                <p className="mb-3 text-sm text-slate-600">
                  Shipped: <strong className="text-slate-900">{qty(item.quantity_shipped)} {item.unit}</strong> of {item.item_name}
                  {item.item_code && <span className="text-slate-400"> ({item.item_code})</span>}
                </p>
                <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
                  <Field label="Item received">
                    <input required maxLength={300} value={line.name} onChange={(e) => update(item.po_item_id, { name: e.target.value })} className={input("lg")} />
                  </Field>
                  <Field label={`Quantity received (${item.unit})`}>
                    <input
                      type="number"
                      inputMode="decimal"
                      required
                      min="0"
                      step="any"
                      value={line.received}
                      onChange={(e) => update(item.po_item_id, { received: e.target.value })}
                      className={input("lg")}
                    />
                  </Field>
                  <Field label={`Accepted, good condition (${item.unit})`}>
                    <input
                      type="number"
                      inputMode="decimal"
                      required
                      min="0"
                      max={line.received || 0}
                      step="any"
                      value={line.accepted}
                      onChange={(e) => update(item.po_item_id, { accepted: e.target.value, acceptedTouched: true })}
                      className={input("lg")}
                    />
                  </Field>
                </div>
                {problems.length > 0 && (
                  <ul className="mt-3 space-y-1 text-sm font-semibold text-brand-red">
                    {problems.map((p) => (
                      <li key={p.type} className="flex items-center gap-1.5">
                        <AlertIcon className="h-4 w-4" />
                        {DISCREPANCY_TYPES[p.type].split(" (")[0]}: {p.message.split(": ").slice(1).join(": ")}
                      </li>
                    ))}
                  </ul>
                )}
              </fieldset>
            );
          })}
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <Field label="Notes" hint="Optional, e.g. pallet condition">
            <textarea maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} className={textareaCls} />
          </Field>
          <Field label="Delivery photos">
            <FilePicker files={deliveryPhotos} onChange={setDeliveryPhotos} label="Add photos" />
          </Field>
        </div>

        {detected.length === 0 && (
          <label className="flex items-start gap-3 rounded-xl border border-blue-100 px-4 py-3">
            <input type="checkbox" checked={otherProblem} onChange={(e) => setOtherProblem(e.target.checked)} className="mt-1 h-5 w-5 accent-[#ed2924]" />
            <span>
              <span className="block text-sm font-bold text-slate-800">Something else is wrong</span>
              <span className="block text-xs text-slate-500">Quantities match, but there is another problem to report.</span>
            </span>
          </label>
        )}

        {declaring && (
          <section className="space-y-4 rounded-2xl border-2 border-red-200 bg-red-50/50 p-5">
            <h3 className="flex items-center gap-2 text-base font-extrabold text-brand-red">
              <AlertIcon />
              Declare discrepancy
            </h3>
            {detected.length > 0 && (
              <p className="text-sm text-slate-700">
                The goods do not match the shipment. Purchasing and the vendor will be alerted about: {detected.map((p) => DISCREPANCY_TYPES[p.type].split(" (")[0].toLowerCase()).join(", ")}.
              </p>
            )}
            {otherProblem && detected.length === 0 && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Problem">
                  <Select value={otherType} onChange={(e) => setOtherType(e.target.value as DiscrepancyType)}>
                    {Object.entries(DISCREPANCY_TYPES).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Item">
                  <Select value={otherItem} onChange={(e) => setOtherItem(e.target.value)}>
                    <option value="">Whole shipment</option>
                    {shipment.items.map((i) => (
                      <option key={i.po_item_id} value={i.po_item_id}>
                        {i.item_name}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
            )}
            <Field label="What happened">
              <textarea required maxLength={1500} value={problemNote} onChange={(e) => setProblemNote(e.target.value)} className={textareaCls} placeholder="e.g. 2 boxes crushed, gloves torn" />
            </Field>
            <Field label="Photos of the problem">
              <FilePicker files={problemPhotos} onChange={setProblemPhotos} label="Add photos" />
            </Field>
          </section>
        )}

        <div className="flex flex-col-reverse gap-3 border-t border-blue-50 pt-5 sm:flex-row sm:justify-end">
          <Link to="/incoming" className={button("secondary", "xl")}>
            Cancel
          </Link>
          <button type="submit" disabled={busy} className={button("red", "xl")}>
            {busy ? <Spinner /> : declaring ? <AlertIcon /> : <CheckIcon className="h-5 w-5" />}
            {declaring ? "Save & declare discrepancy" : "Confirm delivered"}
          </button>
        </div>
      </form>
    </Card>
  );
}
