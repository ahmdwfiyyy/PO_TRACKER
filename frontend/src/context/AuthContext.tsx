import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, getToken, setToken } from "../api/client";
import type { User } from "../api/types";
import type { Notice } from "../components/ui";

// The signed-in user. The role here only decides what the screen shows;
// the backend checks every request, so this is not a security boundary.
type AuthState = {
  user: User | null;
  loading: boolean;
  loginNotice: Notice;
  signIn: (token: string, user: User) => void;
  signOut: (notice?: Notice) => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => getToken() !== null);
  const [loginNotice, setLoginNotice] = useState<Notice>(null);

  const signIn = useCallback((token: string, next: User) => {
    setToken(token);
    setLoginNotice(null);
    setUser(next);
  }, []);

  const signOut = useCallback((notice: Notice = null) => {
    setToken(null);
    setUser(null);
    setLoginNotice(notice);
  }, []);

  // Restore the session on page load
  useEffect(() => {
    if (!getToken()) return;
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  // If the server says the session has ended, go back to the login page
  useEffect(() => {
    const onExpired = () => signOut({ type: "error", text: "Your session has ended. Please sign in again." });
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, [signOut]);

  return <AuthContext.Provider value={{ user, loading, loginNotice, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** The signed-in user, for pages that are only rendered behind RequireAuth. */
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("No signed-in user");
  return user;
}
