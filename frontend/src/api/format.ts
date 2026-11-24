// Formatting helpers. Timestamps come from the API in UTC and are shown in Malaysia time.
const TZ = "Asia/Kuala_Lumpur";

/** Date-only values (YYYY-MM-DD) are calendar dates, so they are shown as-is without timezone shifting. */
export const fmtDate = (value: string | null | undefined) => {
  if (!value) return "—";
  const d = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(value.length === 10 ? {} : { timeZone: TZ }),
  });
};

export const fmtDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TZ,
  });

export const qty = (n: number) => n.toLocaleString("en-MY", { maximumFractionDigits: 3 });

/** Today in Malaysia as YYYY-MM-DD (for date inputs). */
export function today() {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
}

export const ROLE_LABELS = { purchasing: "Purchasing", receiving: "Receiving", vendor: "Vendor" } as const;
