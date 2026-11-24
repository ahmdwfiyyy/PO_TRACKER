import { useState } from "react";
import type { FormEvent } from "react";
import { errorText, sendJson } from "../api/client";
import { Banner, Field, Modal, Spinner, inputCls, redBtn } from "./ui";
import type { Notice } from "./ui";

/** Change your own password (any signed-in user). */
export default function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (next !== confirm) {
      setNotice({ type: "error", text: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await sendJson("/api/auth/change-password", { current_password: current, new_password: next });
      setNotice({ type: "success", text: "Your password has been changed." });
      setDone(true);
    } catch (err) {
      setNotice({ type: "error", text: errorText(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Change password" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Banner notice={notice} />
        {!done && (
          <>
            <Field label="Current password">
              <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} className={inputCls} />
            </Field>
            <Field label="New password" hint="At least 8 characters">
              <input type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} className={inputCls} />
            </Field>
            <Field label="Confirm new password">
              <input type="password" required minLength={8} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputCls} />
            </Field>
          </>
        )}
        <div className="flex justify-end pt-2">
          {done ? (
            <button type="button" className={redBtn} onClick={onClose}>
              Done
            </button>
          ) : (
            <button type="submit" disabled={busy} className={redBtn}>
              {busy && <Spinner />}
              Update password
            </button>
          )}
        </div>
      </form>
    </Modal>
  );
}
