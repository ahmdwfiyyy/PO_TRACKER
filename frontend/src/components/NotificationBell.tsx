import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { fmtDateTime } from "../api/format";
import type { AppNotification, NotificationList } from "../api/types";
import { BellIcon } from "./ui";

const POLL_MS = 60_000;

/** Bell with unread count in the header. Checks for new notifications every minute. */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [data, setData] = useState<NotificationList>({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    api<NotificationList>("/api/notifications")
      .then(setData)
      .catch(() => undefined); // a failed poll is retried next time
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openItem = async (n: AppNotification) => {
    setOpen(false);
    if (!n.is_read) {
      await api(`/api/notifications/${n.id}/read`, { method: "POST" }).catch(() => undefined);
      load();
    }
    if (n.link) navigate(n.link);
  };

  const readAll = async () => {
    await api("/api/notifications/read-all", { method: "POST" }).catch(() => undefined);
    load();
  };

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label={data.unread ? `Notifications, ${data.unread} unread` : "Notifications"}
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
          if (!open) load();
        }}
        className="relative grid h-10 w-10 place-items-center rounded-full bg-white/10 text-white ring-1 ring-white/20 transition hover:bg-white/20"
      >
        <BellIcon className="h-5 w-5" />
        {data.unread > 0 && (
          <span className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-brand-red px-1 text-[10px] font-extrabold text-white ring-2 ring-brand-navy">
            {data.unread > 99 ? "99+" : data.unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-40 w-[min(380px,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-blue-100 bg-white text-slate-900 shadow-[0_24px_60px_rgba(7,27,85,0.25)]">
          <div className="flex items-center justify-between border-b border-blue-50 px-4 py-3">
            <p className="font-extrabold text-brand-navy">Notifications</p>
            {data.unread > 0 && (
              <button type="button" onClick={readAll} className="text-xs font-bold text-brand-blue hover:text-brand-red">
                Mark all as read
              </button>
            )}
          </div>
          {data.items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-slate-500">Nothing yet. Updates on your POs will appear here.</p>
          ) : (
            <ul className="max-h-[420px] overflow-y-auto">
              {data.items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => openItem(n)}
                    className={`flex w-full gap-3 border-b border-blue-50 px-4 py-3 text-left transition hover:bg-brand-ice ${n.is_read ? "" : "bg-blue-50/50"}`}
                  >
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${n.is_read ? "bg-transparent" : "bg-brand-red"}`} aria-hidden="true" />
                    <span className="min-w-0">
                      <span className={`block text-sm ${n.is_read ? "text-slate-600" : "font-semibold text-slate-900"}`}>{n.message}</span>
                      <span className="mt-0.5 block text-xs text-slate-400">
                        {fmtDateTime(n.created_at)}
                        {!n.is_read && <span className="sr-only"> (unread)</span>}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
