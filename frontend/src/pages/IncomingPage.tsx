import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, errorText } from "../api/client";
import type { Page, Shipment } from "../api/types";
import ShipmentCard from "../components/ShipmentCard";
import { Banner, Card, EmptyState, InboxIcon, Loading, redBtn } from "../components/ui";
import type { Notice } from "../components/ui";

type Tab = "incoming" | "received";

/** Receiving's start page: shipments on the way, soonest expected first. */
export default function IncomingPage() {
  const location = useLocation();
  const [tab, setTab] = useState<Tab>("incoming");
  const [shipments, setShipments] = useState<Shipment[] | null>(null);
  const [error, setError] = useState("");
  const [notice] = useState<Notice>(() => {
    const text = (location.state as { notice?: string } | null)?.notice;
    return text ? { type: "success", text } : null;
  });

  useEffect(() => {
    setShipments(null);
    setError("");
    const url = tab === "incoming" ? "/api/shipments?status=ON_THE_WAY&page_size=100" : "/api/shipments?page_size=100";
    api<Page<Shipment>>(url)
      .then((page) =>
        setShipments(
          tab === "incoming"
            ? page.items
            : page.items
                .filter((s) => s.status !== "ON_THE_WAY")
                .sort((a, b) => (b.receipt?.received_at ?? "").localeCompare(a.receipt?.received_at ?? "")),
        ),
      )
      .catch((err) => setError(errorText(err)));
  }, [tab]);

  return (
    <Card
      eyebrow="Receiving"
      title="Incoming shipments"
      description="Open a shipment when the goods arrive at the dock, then count and confirm what came in."
    >
      <Banner notice={error ? { type: "error", text: error } : notice} />

      <div className="mb-5 inline-flex rounded-xl border border-blue-100 bg-brand-ice p-1" role="tablist">
        {(
          [
            ["incoming", "On the way"],
            ["received", "Received"],
          ] as [Tab, string][]
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`rounded-lg px-5 py-2.5 text-sm font-bold transition ${tab === value ? "bg-white text-brand-navy shadow-sm" : "text-slate-500 hover:text-brand-navy"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {!shipments && !error && <Loading />}
      {shipments && shipments.length === 0 && (
        <EmptyState
          title={tab === "incoming" ? "Nothing on the way" : "Nothing received yet"}
          text={tab === "incoming" ? "Shipments appear here as soon as a vendor dispatches them." : undefined}
        />
      )}
      {shipments && shipments.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {shipments.map((s) => (
            <ShipmentCard
              key={s.id}
              shipment={s}
              showPo
              actions={
                s.status === "ON_THE_WAY" && (
                  <Link to={`/shipments/${s.id}/receive`} className={`${redBtn} w-full sm:w-auto`}>
                    <InboxIcon className="h-4 w-4" />
                    Receive this shipment
                  </Link>
                )
              }
            />
          ))}
        </div>
      )}
    </Card>
  );
}
