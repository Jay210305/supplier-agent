import { NavLink, Outlet, Route, Routes, Navigate } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import SourcesPage from "./pages/SourcesPage";

function Layout() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? "bg-emerald-500/20 text-emerald-300"
        : "text-slate-300 hover:text-slate-100 hover:bg-slate-800"
    }`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-6">
          <h1 className="text-lg font-semibold tracking-tight text-emerald-300">
            Supplier Agent
          </h1>
          <nav className="flex gap-1">
            <NavLink to="/" className={linkClass} end>
              Dashboard
            </NavLink>
            <NavLink to="/sources" className={linkClass}>
              Fuentes externas
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="sources" element={<SourcesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
