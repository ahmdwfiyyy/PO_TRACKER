import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorText, sendJson } from "../api/client";
import type { User } from "../api/types";
import { ArrowIcon, Banner, Field, Logo, Spinner, TopBar, inputCls, panel, redBtn } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { user, signIn, loginNotice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (user) return <Navigate to={from} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await sendJson<{ token: string; user: User }>("/api/auth/login", { email, password });
      signIn(data.token, data.user);
      navigate(from, { replace: true });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <div className="brand-grid relative flex min-h-screen items-center justify-center overflow-hidden bg-brand-navy px-4 py-10">
      <div className="brand-ribbon pointer-events-none absolute -right-16 -top-32 h-80 w-96 opacity-80" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 h-64 w-64 rounded-full border-[40px] border-white/5" />
      <div className="pointer-events-none absolute -bottom-20 right-24 h-44 w-44 rounded-full bg-brand-red/20 blur-2xl" />
      <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-brand-red via-white to-brand-bright" />

      <div className="relative w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3 text-white">
          <Logo size="h-14 w-14" img="h-10 w-10" />
          <div>
            <p className="text-xl font-extrabold tracking-[-0.02em]">Carsem PO Tracker</p>
            <p className="text-xs font-medium tracking-wide text-blue-100">Purchase order delivery tracking</p>
          </div>
        </div>

        <section className={panel}>
          <TopBar />
          <div className="border-b border-blue-50 bg-gradient-to-r from-white to-brand-ice px-6 py-6">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-[0.14em] text-brand-red">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-red" />
              Secure access
            </div>
            <h1 className="text-2xl font-extrabold tracking-[-0.02em] text-brand-navy">Welcome back</h1>
            <p className="mt-1 text-sm text-slate-500">Sign in to see and update purchase order deliveries.</p>
          </div>

          <form onSubmit={submit} className="space-y-5 p-6">
            <Banner notice={error ? { type: "error", text: error } : loginNotice} />

            <Field label="Email">
              <input
                type="email"
                required
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
              />
            </Field>

            <Field label="Password">
              <div className="relative">
                <input
                  type={show ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputCls} pr-20`}
                />
                <button
                  type="button"
                  onClick={() => setShow((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-bold text-brand-blue hover:text-brand-red"
                >
                  {show ? "Hide" : "Show"}
                </button>
              </div>
            </Field>

            <button type="submit" disabled={busy} className={`${redBtn} w-full`}>
              {busy ? (
                <>
                  <Spinner />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <ArrowIcon />
                </>
              )}
            </button>
          </form>
        </section>

        <p className="mt-5 text-center text-xs text-blue-100">No account yet, or forgot your password? Contact Carsem Purchasing.</p>
      </div>
    </div>
  );
}
