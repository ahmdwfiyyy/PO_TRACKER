import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, sendJson } from "../api/client";
import { ROLE_LABELS, fmtDate } from "../api/format";
import type { Role, User, Vendor } from "../api/types";
import {
  Badge,
  Banner,
  Card,
  EditIcon,
  EmptyState,
  Field,
  Loading,
  Modal,
  PlusIcon,
  Select,
  Spinner,
  button,
  inputCls,
  redBtn,
  smallBtn,
  tableHead,
  td,
  th,
} from "../components/ui";
import type { Notice, Tone } from "../components/ui";
import { useUser } from "../context/AuthContext";

const ROLE_TONE: Record<Role, Tone> = { purchasing: "red", receiving: "blue", vendor: "amber" };

function FormButtons({ busy, label, onClose }: { busy: boolean; label: string; onClose: () => void }) {
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

// ---------------------------------------------------------------------------
function VendorModal({ vendor, onClose, onSaved }: { vendor: Vendor | null; onClose: () => void; onSaved: (text: string) => void }) {
  const [form, setForm] = useState({
    name: vendor?.name ?? "",
    contact_person: vendor?.contact_person ?? "",
    email: vendor?.email ?? "",
    phone: vendor?.phone ?? "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = {
      name: form.name,
      contact_person: form.contact_person || null,
      email: form.email || null,
      phone: form.phone || null,
    };
    try {
      if (vendor) await sendJson(`/api/vendors/${vendor.id}`, body, "PATCH");
      else await sendJson("/api/vendors", body);
      onSaved(vendor ? `${form.name} was updated.` : `${form.name} was added. Now create a login for them under Users.`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <Modal title={vendor ? `Edit ${vendor.name}` : "Add vendor"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <Field label="Company name">
          <input required maxLength={200} value={form.name} onChange={set("name")} className={inputCls} />
        </Field>
        <Field label="Contact person">
          <input maxLength={200} value={form.contact_person} onChange={set("contact_person")} className={inputCls} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Email" hint="Delivery updates are emailed here">
            <input type="email" maxLength={254} value={form.email} onChange={set("email")} className={inputCls} />
          </Field>
          <Field label="Phone">
            <input maxLength={50} value={form.phone} onChange={set("phone")} className={inputCls} />
          </Field>
        </div>
        <FormButtons busy={busy} label={vendor ? "Save" : "Add vendor"} onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
function AddUserModal({ vendors, onClose, onSaved }: { vendors: Vendor[]; onClose: () => void; onSaved: (text: string) => void }) {
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "vendor" as Role, vendor_id: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await sendJson("/api/users", {
        ...form,
        vendor_id: form.role === "vendor" ? Number(form.vendor_id) : null,
      });
      onSaved(`Account created for ${form.name}. Share the email and temporary password with them.`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title="Add user" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <Field label="Role">
          <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="vendor">Vendor - sees only their own POs, dispatches shipments</option>
            <option value="receiving">Receiving - records deliveries at the dock</option>
            <option value="purchasing">Purchasing - full access</option>
          </Select>
        </Field>
        {form.role === "vendor" && (
          <Field label="Vendor company">
            <Select required value={form.vendor_id} onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}>
              <option value="">Choose a vendor</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Full name">
          <input required maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
        </Field>
        <Field label="Email" hint="Used to sign in">
          <input type="email" required autoCapitalize="none" spellCheck={false} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputCls} />
        </Field>
        <Field label="Temporary password" hint="At least 8 characters. They can change it after signing in.">
          <input required minLength={8} autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputCls} />
        </Field>
        <FormButtons busy={busy} label="Create account" onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
function EditUserModal({ user, isSelf, onClose, onSaved }: { user: User; isSelf: boolean; onClose: () => void; onSaved: (text: string) => void }) {
  const [name, setName] = useState(user.name);
  const [isActive, setIsActive] = useState(user.is_active);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await sendJson(`/api/users/${user.id}`, { name, is_active: isActive, ...(password ? { password } : {}) }, "PATCH");
      onSaved(`${name}'s account was updated${password ? " and the password reset" : ""}.`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={`Edit ${user.email}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={error ? { type: "error", text: error } : null} />
        <Field label="Full name">
          <input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
        </Field>
        <label className={`flex items-start gap-3 rounded-xl border border-blue-100 px-4 py-3 ${isSelf ? "opacity-50" : ""}`}>
          <input type="checkbox" disabled={isSelf} checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="mt-1 h-4 w-4 accent-[#0b3c91]" />
          <span>
            <span className="block text-sm font-bold text-slate-800">Account active</span>
            <span className="block text-xs text-slate-500">
              {isSelf ? "You cannot deactivate your own account." : "A deactivated account cannot sign in. Its POs and history are kept."}
            </span>
          </span>
        </label>
        <Field label="Reset password" hint="Leave empty to keep the current password">
          <input minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
        </Field>
        <FormButtons busy={busy} label="Save" onClose={onClose} />
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
type Dialog = { kind: "vendor"; vendor: Vendor | null } | { kind: "addUser" } | { kind: "editUser"; user: User } | null;

export default function AdminPage() {
  const me = useUser();
  const [vendors, setVendors] = useState<Vendor[] | null>(null);
  const [users, setUsers] = useState<User[] | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [dialog, setDialog] = useState<Dialog>(null);

  const load = useCallback(() => {
    Promise.all([api<Vendor[]>("/api/vendors"), api<User[]>("/api/users")])
      .then(([v, u]) => {
        setVendors(v);
        setUsers(u);
      })
      .catch((err) => setNotice({ type: "error", text: errorText(err) }));
  }, []);
  useEffect(load, [load]);

  const saved = (text: string) => {
    setDialog(null);
    setNotice({ type: "success", text });
    load();
  };

  if (!vendors || !users) return notice ? <Banner notice={notice} /> : <Loading />;

  return (
    <div className="space-y-7">
      <Banner notice={notice} />

      <Card
        eyebrow="Purchasing"
        title="Vendors"
        description="Vendor companies are never deleted, so their delivery history stays on record."
        actions={
          <button type="button" className={redBtn} onClick={() => setDialog({ kind: "vendor", vendor: null })}>
            <PlusIcon className="h-4 w-4" />
            Add vendor
          </button>
        }
        bodyClassName="p-0"
      >
        {vendors.length === 0 ? (
          <div className="p-5 sm:p-7">
            <EmptyState title="No vendors yet" text="Add the first vendor, then create a login for them." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left text-sm">
              <thead className={tableHead}>
                <tr>
                  <th className={th}>Vendor</th>
                  <th className={th}>Contact</th>
                  <th className={`${th} text-right`}>Logins</th>
                  <th className={`${th} text-right`}>Open POs</th>
                  <th className={`${th} text-right`}>All POs</th>
                  <th className={th} />
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} className="border-t border-blue-50">
                    <td className={`${td} font-bold text-brand-navy`}>{v.name}</td>
                    <td className={`${td} text-slate-600`}>
                      <p>{v.contact_person ?? "—"}</p>
                      <p className="text-xs text-slate-400">{[v.email, v.phone].filter(Boolean).join(" · ")}</p>
                    </td>
                    <td className={`${td} text-right tabular-nums`}>
                      {v.user_count === 0 ? <Badge tone="amber">None</Badge> : v.user_count}
                    </td>
                    <td className={`${td} text-right tabular-nums`}>{v.open_po_count}</td>
                    <td className={`${td} text-right tabular-nums`}>{v.po_count}</td>
                    <td className={`${td} text-right`}>
                      <button type="button" className={smallBtn} onClick={() => setDialog({ kind: "vendor", vendor: v })}>
                        <EditIcon className="h-3.5 w-3.5" />
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card
        eyebrow="Purchasing"
        title="Users"
        description="Vendor logins, Receiving staff and Purchasing staff."
        actions={
          <button type="button" className={redBtn} onClick={() => setDialog({ kind: "addUser" })}>
            <PlusIcon className="h-4 w-4" />
            Add user
          </button>
        }
        bodyClassName="p-0"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left text-sm">
            <thead className={tableHead}>
              <tr>
                <th className={th}>Name</th>
                <th className={th}>Role</th>
                <th className={th}>Vendor</th>
                <th className={th}>Status</th>
                <th className={th}>Created</th>
                <th className={th} />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className={`border-t border-blue-50 ${u.is_active ? "" : "text-slate-400"}`}>
                  <td className={td}>
                    <p className="font-bold">{u.name}</p>
                    <p className="text-xs text-slate-400">{u.email}</p>
                  </td>
                  <td className={td}>
                    <Badge tone={ROLE_TONE[u.role]}>{ROLE_LABELS[u.role]}</Badge>
                  </td>
                  <td className={`${td} text-slate-600`}>{u.vendor_name ?? "—"}</td>
                  <td className={td}>{u.is_active ? <Badge tone="green">Active</Badge> : <Badge>Deactivated</Badge>}</td>
                  <td className={`${td} whitespace-nowrap text-slate-600`}>{fmtDate(u.created_at)}</td>
                  <td className={`${td} text-right`}>
                    <button type="button" className={smallBtn} onClick={() => setDialog({ kind: "editUser", user: u })}>
                      <EditIcon className="h-3.5 w-3.5" />
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {dialog?.kind === "vendor" && <VendorModal vendor={dialog.vendor} onClose={() => setDialog(null)} onSaved={saved} />}
      {dialog?.kind === "addUser" && <AddUserModal vendors={vendors} onClose={() => setDialog(null)} onSaved={saved} />}
      {dialog?.kind === "editUser" && (
        <EditUserModal user={dialog.user} isSelf={dialog.user.id === me.id} onClose={() => setDialog(null)} onSaved={saved} />
      )}
    </div>
  );
}
