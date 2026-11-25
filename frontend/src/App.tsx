import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { Role } from "./api/types";
import Layout from "./components/Layout";
import { EmptyState, Loading } from "./components/ui";
import { useAuth } from "./context/AuthContext";
import AdminPage from "./pages/AdminPage";
import IncomingPage from "./pages/IncomingPage";
import ReceivePage from "./pages/ReceivePage";
import LoginPage from "./pages/LoginPage";
import PoDetailPage from "./pages/PoDetailPage";
import PoFormPage from "./pages/PoFormPage";
import PoListPage from "./pages/PoListPage";

/** Signed-in users only; anyone else goes to the login page (and comes back afterwards). */
function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

/** Hides pages from other roles. The backend enforces the same rule on every request. */
function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return <EmptyState title="You do not have access to this page" text="Use the menu above to go back." />;
  }
  return <>{children}</>;
}

/** Each role's start page. */
function Home() {
  const { user } = useAuth();
  return <Navigate to={user?.role === "receiving" ? "/incoming" : "/pos"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Home />} />
        <Route
          path="/incoming"
          element={
            <RequireRole roles={["receiving"]}>
              <IncomingPage />
            </RequireRole>
          }
        />
        <Route
          path="/shipments/:id/receive"
          element={
            <RequireRole roles={["receiving"]}>
              <ReceivePage />
            </RequireRole>
          }
        />
        <Route path="/pos" element={<PoListPage />} />
        <Route
          path="/pos/new"
          element={
            <RequireRole roles={["purchasing"]}>
              <PoFormPage />
            </RequireRole>
          }
        />
        <Route path="/pos/:id" element={<PoDetailPage />} />
        <Route
          path="/pos/:id/edit"
          element={
            <RequireRole roles={["purchasing"]}>
              <PoFormPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireRole roles={["purchasing"]}>
              <AdminPage />
            </RequireRole>
          }
        />
        <Route path="*" element={<EmptyState title="Page not found" text="Use the menu above to find your way back." />} />
      </Route>
    </Routes>
  );
}
