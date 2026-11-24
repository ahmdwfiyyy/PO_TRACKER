import type { POStatus, ShipmentStatus } from "../api/types";
import { AlertIcon, Badge, ClockIcon } from "./ui";
import type { Tone } from "./ui";

// One colour per status, used everywhere so a status always looks the same.
const PO_STATUS: Record<POStatus, [string, Tone]> = {
  ISSUED: ["Issued", "slate"],
  PREPARING: ["Preparing", "amber"],
  ON_THE_WAY: ["On the way", "blue"],
  PARTIALLY_DELIVERED: ["Partially delivered", "violet"],
  DELIVERED: ["Delivered", "green"],
  CANCELLED: ["Cancelled", "navy"],
};

const SHIPMENT_STATUS: Record<ShipmentStatus, [string, Tone]> = {
  ON_THE_WAY: ["On the way", "blue"],
  DELIVERED: ["Delivered", "green"],
  DISCREPANCY: ["Discrepancy", "red"],
  RESOLVED: ["Resolved", "slate"],
};

export const PO_STATUS_OPTIONS = Object.entries(PO_STATUS).map(([value, [label]]) => ({ value: value as POStatus, label }));

export const statusLabel = (status: string) =>
  (PO_STATUS as Record<string, [string, Tone]>)[status]?.[0] ??
  (SHIPMENT_STATUS as Record<string, [string, Tone]>)[status]?.[0] ??
  status;

export function POStatusBadge({ status }: { status: POStatus }) {
  const [label, tone] = PO_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

export function ShipmentStatusBadge({ status }: { status: ShipmentStatus }) {
  const [label, tone] = SHIPMENT_STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

/** The red "open discrepancy" and "overdue" flags shown next to a status. */
export function Flags({ overdue, discrepancy }: { overdue?: boolean; discrepancy?: boolean }) {
  return (
    <>
      {discrepancy && (
        <Badge tone="red">
          <AlertIcon className="h-3 w-3" />
          Discrepancy
        </Badge>
      )}
      {overdue && (
        <Badge tone="redSoft">
          <ClockIcon className="h-3 w-3" />
          Overdue
        </Badge>
      )}
    </>
  );
}
