import React, { useEffect, useState } from "react";
import { Outlet, NavLink, Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  Activity,
  MessageSquare,
  BarChart3,
  PanelLeft,
  LogOut,
  Menu,
  X,
  CreditCard,
  Shield,
  Send,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useMode } from "../../context/ModeContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/analysis", label: "Analysis", icon: Activity, alsoMatches: "/report/" },
  { to: "/chat", label: "AI CFO", icon: MessageSquare },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/billing", label: "Billing", icon: CreditCard },
  { to: "/banking", label: "Banking", icon: Send },
  { to: "/security", label: "Security", icon: Shield },
];

const FALLBACK_MODES = [
  { id: "aws", label: "AWS Mode" },
  { id: "local", label: "Local Mode" },
];

const COLLAPSE_KEY = "cashflow-sidebar-collapsed";

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

function SidebarContent({ collapsed, onNavigate }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const initial = (user?.company_name || user?.email || "C").charAt(0).toUpperCase();

  return (
    <div className="flex h-full flex-col">
      <Link
        to="/"
        onClick={onNavigate}
        className={`flex h-16 items-center gap-3 border-b border-[var(--border-color)] ${collapsed ? "justify-center px-0" : "px-5"}`}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--primary-accent)] font-display text-xl leading-none text-[#0a0a0a]">
          C
        </span>
        {!collapsed && (
          <span className="flex flex-col leading-none">
            <span className="font-display text-2xl tracking-wider text-[var(--text-primary)]">C.A.S.H.F.L.O.W</span>
            <span className="mt-1 text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">AI CFO Console</span>
          </span>
        )}
      </Link>

      <nav aria-label="Dashboard" className="flex-1 overflow-y-auto px-3 py-5">
        {!collapsed && (
          <p className="mb-3 px-2 text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Tools</p>
        )}
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, alsoMatches }) => {
            const forcedActive = alsoMatches && pathname.startsWith(alsoMatches);
            return (
              <li key={to}>
                <NavLink
                  to={to}
                  end
                  onClick={onNavigate}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) => {
                    const active = isActive || forcedActive;
                    return `group flex items-center gap-3 rounded-md px-2.5 py-2.5 text-xs uppercase tracking-[0.15em] transition-colors ${
                      collapsed ? "justify-center" : ""
                    } ${
                      active
                        ? "bg-[var(--primary-accent)] text-[#0a0a0a]"
                        : "text-[var(--nav-link-color)] hover:bg-[var(--surface-raised)] hover:text-[var(--text-primary)]"
                    }`;
                  }}
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {collapsed ? <span className="sr-only">{label}</span> : <span>{label}</span>}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-[var(--border-color)] p-3">
        <div className={`flex items-center gap-3 rounded-md bg-[var(--surface-raised)] p-2.5 ${collapsed ? "justify-center" : ""}`}>
          <span
            aria-hidden="true"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-[var(--border-color)] font-display text-lg text-[var(--primary-accent)]"
          >
            {initial}
          </span>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs text-[var(--text-primary)]">{user?.company_name || "Your company"}</p>
              <p className="truncate text-[10px] text-[var(--text-muted)]">{user?.email}</p>
            </div>
          )}
          {!collapsed && (
            <button
              type="button"
              onClick={handleLogout}
              aria-label="Log out"
              className="rounded p-1.5 text-[var(--text-muted)] transition-colors hover:text-[var(--negative-color)]"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
        {collapsed && (
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Log out"
            className="mt-2 flex w-full justify-center rounded-md p-2 text-[var(--text-muted)] transition-colors hover:text-[var(--negative-color)]"
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export default function DashboardLayout() {
  const { mode, modes, setMode, loading: modeLoading } = useMode();
  const { pathname } = useLocation();
  const now = useClock();
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === "1");
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      return !c;
    });
  };

  const current =
    NAV_ITEMS.find((item) => pathname === item.to || (item.alsoMatches && pathname.startsWith(item.alsoMatches))) ||
    NAV_ITEMS[0];
  const crumb = pathname.startsWith("/report/") ? "Report" : current.label;

  return (
    <div className="app-shell flex h-[100dvh] overflow-hidden bg-[var(--bg-color)]">
      <aside
        className={`hidden shrink-0 border-r border-[var(--border-color)] bg-[var(--surface-card)] transition-[width] duration-200 md:block ${
          collapsed ? "w-[72px]" : "w-64"
        }`}
      >
        <SidebarContent collapsed={collapsed} />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/70"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative h-full w-72 border-r border-[var(--border-color)] bg-[var(--surface-card)]">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation"
              className="absolute right-3 top-5 z-10 p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-[var(--border-color)] bg-[var(--bg-color)] px-4 md:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="rounded-md border border-[var(--border-color)] p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] md:hidden"
            >
              <Menu className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-pressed={collapsed}
              className="hidden rounded-md border border-[var(--border-color)] p-1.5 text-[var(--text-secondary)] transition-colors hover:border-[var(--primary-accent)] hover:text-[var(--primary-accent)] md:block"
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[11px] uppercase tracking-[0.15em]">
              <span className="text-[var(--text-muted)]">Console</span>
              <span className="text-[var(--text-muted)]">/</span>
              <span className="truncate text-[var(--text-primary)]" aria-current="page">{crumb}</span>
            </nav>
          </div>

          <div className="flex items-center gap-4 text-[11px]">
            <time
              dateTime={now.toISOString()}
              className="hidden tabular-nums uppercase tracking-[0.15em] text-[var(--text-muted)] lg:block"
            >
              {now.toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short" })}
              {" · "}
              {now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </time>
            <label className="flex items-center gap-2 text-[var(--nav-link-color)]">
              <span className="hidden items-center gap-1.5 uppercase tracking-[0.15em] sm:flex">
                <span
                  aria-hidden="true"
                  className={`h-1.5 w-1.5 rounded-full ${modeLoading ? "bg-[var(--text-muted)]" : "bg-[var(--positive-color)]"}`}
                />
                Mode
              </span>
              <select
                value={mode}
                disabled={modeLoading}
                onChange={(e) => setMode(e.target.value)}
                className="rounded-md border border-[var(--border-color)] bg-[var(--surface-card)] px-2 py-1.5 uppercase tracking-wider text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none"
              >
                {(modes.length ? modes : FALLBACK_MODES).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label || option.id}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1400px] p-4 md:p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
