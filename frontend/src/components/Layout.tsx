import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { ROLE_LABELS } from "../api/format";
import type { Role } from "../api/types";
import { useUser, useAuth } from "../context/AuthContext";
import ChangePasswordModal from "./ChangePasswordModal";
import NotificationBell from "./NotificationBell";
import { AlertIcon, Brand, BuildingIcon, ChartIcon, ClipboardIcon, KeyIcon, TruckIcon } from "./ui";

// Menu per role. Later phases add Dashboard, Incoming shipments and Discrepancies here.
const NAV: Record<Role, [string, string, ReactNode][]> = {
  purchasing: [
    ["/dashboard", "Dashboard", <ChartIcon key="d" />],
    ["/pos", "Purchase orders", <ClipboardIcon key="p" />],
    ["/discrepancies", "Discrepancies", <AlertIcon key="x" />],
    ["/admin", "Vendors & users", <BuildingIcon key="v" />],
  ],
  vendor: [["/pos", "My purchase orders", <ClipboardIcon key="p" />]],
  receiving: [
    ["/incoming", "Incoming shipments", <TruckIcon key="i" />],
    ["/pos", "Purchase orders", <ClipboardIcon key="p" />],
  ],
};

function Header({ onChangePassword }: { onChangePassword: () => void }) {
  const user = useUser();
  const { signOut } = useAuth();
  return (
    // No overflow-hidden on the header itself: it would clip the notification dropdown.
    // Only the decoration layer is clipped, and z-30 keeps the header (and dropdown) above the page.
    <header className="brand-grid relative z-30 bg-brand-navy text-white shadow-[0_8px_30px_rgba(7,27,85,0.18)]">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className="brand-ribbon absolute -right-16 -top-32 h-80 w-96 opacity-80" />
      </div>
      <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-brand-red via-white to-brand-bright" />

      <div className="relative mx-auto flex h-[84px] max-w-[1180px] items-center justify-between gap-3 px-5 sm:px-8">
        <Brand />
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden text-right md:block">
            <p className="text-sm font-bold leading-tight">{user.name}</p>
            <p className="text-[11px] uppercase tracking-wide text-blue-100">
              {user.role === "vendor" && user.vendor_name ? user.vendor_name : ROLE_LABELS[user.role]}
            </p>
          </div>
          <NotificationBell />
          <button
            type="button"
            onClick={onChangePassword}
            aria-label="Change password"
            title="Change password"
            className="grid h-10 w-10 place-items-center rounded-full bg-white/10 text-white ring-1 ring-white/20 transition hover:bg-white/20"
          >
            <KeyIcon className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => signOut()}
            className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-white/10 px-4 py-2.5 text-xs font-bold text-white ring-1 ring-white/20 transition hover:bg-white/20"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}

export default function Layout() {
  const user = useUser();
  const [changingPassword, setChangingPassword] = useState(false);

  return (
    <div className="flex min-h-screen flex-col bg-brand-ice text-slate-950">
      <Header onChangePassword={() => setChangingPassword(true)} />

      <main className="panel-glow mx-auto w-full max-w-[1180px] flex-1 px-4 py-7 sm:px-8 sm:py-10">
        <nav
          aria-label="Sections"
          className="mb-7 flex w-full gap-1.5 overflow-x-auto rounded-2xl border border-blue-100 bg-white p-1.5 shadow-[0_6px_24px_rgba(7,27,85,0.07)]"
        >
          {NAV[user.role].map(([to, label, icon]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold transition-all ${
                  isActive
                    ? "bg-brand-blue text-white shadow-[0_5px_14px_rgba(11,60,145,0.25)]"
                    : "text-slate-600 hover:bg-brand-ice hover:text-brand-navy"
                }`
              }
            >
              {icon}
              {label}
            </NavLink>
          ))}
        </nav>
        <Outlet />
      </main>

      <footer className="border-t border-blue-100 py-6 text-center text-xs font-medium text-slate-500">
        CARSEM PO TRACKER | WAFIY 2026
      </footer>

      {changingPassword && <ChangePasswordModal onClose={() => setChangingPassword(false)} />}
    </div>
  );
}
