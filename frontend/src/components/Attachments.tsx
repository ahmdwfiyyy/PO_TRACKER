import { useRef, useState } from "react";
import { UPLOAD_ACCEPT, download, errorText, uploadFiles } from "../api/client";
import type { Attachment, EntityType } from "../api/types";
import { CloseIcon, PaperclipIcon, Spinner, smallBtn } from "./ui";

const sizeText = (bytes: number) => (bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`);

/** Download links for attached files (downloads go through the authenticated API). */
export function FileList({ files }: { files: Attachment[] }) {
  const [error, setError] = useState("");
  if (files.length === 0) return null;
  return (
    <div>
      <ul className="flex flex-wrap gap-2">
        {files.map((f) => (
          <li key={f.id}>
            <button
              type="button"
              onClick={() => download(`/api/attachments/${f.id}`, f.filename).catch((err) => setError(errorText(err)))}
              title={`${f.filename} · ${sizeText(f.size)}${f.uploaded_by_name ? ` · ${f.uploaded_by_name}` : ""}`}
              className="inline-flex max-w-[240px] items-center gap-1.5 rounded-lg border border-blue-100 bg-white px-3 py-1.5 text-xs font-semibold text-brand-blue transition hover:border-brand-blue hover:bg-brand-ice"
            >
              <PaperclipIcon className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{f.filename}</span>
            </button>
          </li>
        ))}
      </ul>
      {error && <p className="mt-1 text-xs text-brand-red">{error}</p>}
    </div>
  );
}

/** Pick files to upload later (e.g. together with a form). */
export function FilePicker({ files, onChange, label = "Add files" }: { files: File[]; onChange: (files: File[]) => void; label?: string }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2">
      <input
        ref={input}
        type="file"
        multiple
        accept={UPLOAD_ACCEPT}
        className="hidden"
        onChange={(e) => {
          onChange([...files, ...Array.from(e.target.files ?? [])]);
          e.target.value = "";
        }}
      />
      <button type="button" className={smallBtn} onClick={() => input.current?.click()}>
        <PaperclipIcon className="h-3.5 w-3.5" />
        {label}
      </button>
      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center gap-2 text-xs text-slate-600">
              <span className="truncate">{f.name}</span>
              <span className="text-slate-400">{sizeText(f.size)}</span>
              <button
                type="button"
                aria-label={`Remove ${f.name}`}
                className="rounded p-0.5 text-slate-400 hover:text-brand-red"
                onClick={() => onChange(files.filter((_, j) => j !== i))}
              >
                <CloseIcon className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[11px] text-slate-400">PDF, JPG or PNG, up to 10 MB each</p>
    </div>
  );
}

/** Upload straight away (e.g. a vendor adding a DO to an existing shipment). */
export function UploadButton({
  entityType,
  entityId,
  label,
  onUploaded,
}: {
  entityType: EntityType;
  entityId: number;
  label: string;
  onUploaded: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const upload = async (files: File[]) => {
    if (files.length === 0) return;
    setBusy(true);
    setError("");
    const errors = await uploadFiles(entityType, entityId, files);
    setBusy(false);
    if (errors.length) setError(errors.join(" "));
    onUploaded();
  };

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <input
        ref={input}
        type="file"
        multiple
        accept={UPLOAD_ACCEPT}
        className="hidden"
        onChange={(e) => {
          upload(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
      <button type="button" className={smallBtn} disabled={busy} onClick={() => input.current?.click()}>
        {busy ? <Spinner className="border-brand-blue/30 border-t-brand-blue" /> : <PaperclipIcon className="h-3.5 w-3.5" />}
        {label}
      </button>
      {error && <span className="text-xs text-brand-red">{error}</span>}
    </span>
  );
}
