import React, { useState } from "react";
import { Outlet, NavLink, Link, useNavigate } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useMode } from "../../context/ModeContext";

const BASE_NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/documents", label: "Documents" },
  { to: "/analysis", label: "Analysis" },
  { to: "/chat", label: "AI CFO" },
  { to: "/reports", label: "Reports" },
];

const FALLBACK_MODES = [
  { id: "aws", label: "AWS Mode" },
  { id: "local", label: "Local Mode" },
];

function navClass({ isActive }) {
  return `relative px-3 py-2 uppercase tracking-[0.15em] transition-colors ${
    isActive
      ? "text-[var(--text-primary)] after:absolute after:inset-x-3 after:-bottom-[13px] after:h-px after:bg-[var(--primary-accent)]"
      : "text-[var(--nav-link-color)] hover:text-[var(--text-primary)]"
  }`;
}

export default function ThemeLayout() {
  const { user, logout, isAuthenticated } = useAuth();
  const { mode, modes, setMode, loading: modeLoading } = useMode();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const navItems = isAuthenticated
    ? [...BASE_NAV_ITEMS, { to: "/billing", label: "Billing" }]
    : BASE_NAV_ITEMS;

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen flex-col bg-[var(--bg-color)]">
      <header
        className="sticky top-0 z-20 border-b backdrop-blur"
        style={{ backgroundColor: "var(--nav-bg)", borderColor: "var(--nav-border)" }}
      >
        <nav className="mx-auto flex h-14 max-w-[1280px] items-center justify-between gap-6 px-6" aria-label="Main">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-6 w-6 items-center justify-center bg-[var(--primary-accent)] font-display text-base leading-none text-[#0a0a0a]">
              C
            </span>
            <span className="font-display text-2xl leading-none tracking-wider text-[var(--text-primary)]">
              CASHFLOW
            </span>
          </Link>

          <div className="hidden flex-1 justify-center text-[11px] md:flex">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} end className={navClass}>
                {item.label}
              </NavLink>
            ))}
          </div>

          <div className="flex items-center gap-3 text-[11px]">
            <label className="hidden items-center gap-2 text-[var(--nav-link-color)] sm:flex">
              <span className="flex items-center gap-1.5 uppercase tracking-[0.15em]">
                <span
                  aria-hidden="true"
                  className={`h-1.5 w-1.5 ${modeLoading ? "bg-[var(--text-muted)]" : "bg-[var(--positive-color)]"}`}
                />
                Mode
              </span>
              <select
                value={mode}
                disabled={modeLoading}
                onChange={(e) => setMode(e.target.value)}
                className="border border-[var(--border-color)] bg-[var(--surface-card)] px-2 py-1.5 uppercase tracking-wider text-[var(--text-primary)] focus:border-[var(--primary-accent)] focus:outline-none"
              >
                {(modes.length ? modes : FALLBACK_MODES).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label || option.id}
                  </option>
                ))}
              </select>
            </label>

            {isAuthenticated ? (
              <>
                <span className="hidden max-w-[180px] truncate text-[var(--text-muted)] lg:block">{user?.email}</span>
                <button
                  onClick={handleLogout}
                  className="btn-outline px-3 py-1.5 uppercase tracking-[0.15em]"
                >
                  Logout
                </button>
              </>
            ) : (
              <Link to="/login" className="btn-primary px-3 py-1.5 uppercase tracking-[0.15em]">
                Login
              </Link>
            )}

            <button
              type="button"
              className="p-1 text-[var(--text-primary)] md:hidden"
              onClick={() => setMenuOpen((o) => !o)}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "Close menu" : "Open menu"}
            >
              {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </nav>

        {menuOpen && (
          <div className="flex flex-col border-t border-[var(--border-color)] px-6 py-3 text-xs md:hidden">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `py-2.5 uppercase tracking-[0.15em] ${isActive ? "text-[var(--primary-accent)]" : "text-[var(--nav-link-color)]"}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        )}
      </header>

      <main className="mx-auto w-full max-w-[1280px] flex-1 px-6">
        <Outlet />
      </main>
    </div>
  );
}
