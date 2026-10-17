import React, { useState, useEffect } from "react";
import { Outlet, NavLink, Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useMode } from "../../context/ModeContext";

export default function ThemeLayout() {
  const { user, logout } = useAuth();
  const { mode, modes, setMode, loading: modeLoading } = useMode();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col">
      <nav
        className="sticky top-0 z-10 h-14 flex items-center justify-between px-6 border-b"
        style={{
          backgroundColor: "var(--nav-bg)",
          borderColor: "var(--nav-border)",
        }}
      >
          <Link to="/" className="flex items-center space-x-3 text-decoration-none">
            <div
              className="w-8 h-8 flex items-center justify-center font-bold text-base"
              style={{
                border: "1px solid var(--primary-accent)",
                color: "var(--primary-accent)",
                backgroundColor: "var(--surface-card)",
              }}
            >
              C
            </div>
            <span
              className="font-bold tracking-widest text-lg"
              style={{ color: "var(--text-primary)" }}
            >
              CASHFLOW
            </span>
          </Link>

        <div className="hidden md:flex flex-1 justify-center space-x-2 font-mono text-[12px] tracking-wider">
          <NavLink
            to="/dashboard"
            end
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "bg-[var(--surface-card)] shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? { color: "var(--primary-accent)" }
                : { color: "var(--nav-link-color)" }
            }
          >
            DASHBOARD
          </NavLink>
          <NavLink
            to="/documents"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "bg-[var(--surface-card)] shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? { color: "var(--primary-accent)" }
                : { color: "var(--nav-link-color)" }
            }
          >
            DOCUMENTS
          </NavLink>
          <NavLink
            to="/analysis"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "bg-[var(--surface-card)] shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? { color: "var(--primary-accent)" }
                : { color: "var(--nav-link-color)" }
            }
          >
            ANALYSIS
          </NavLink>
          <NavLink
            to="/chat"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "bg-[var(--surface-card)] shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? { color: "var(--primary-accent)" }
                : { color: "var(--nav-link-color)" }
            }
          >
            AI CFO
          </NavLink>
          <NavLink
            to="/reports"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "bg-[var(--surface-card)] shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? { color: "var(--primary-accent)" }
                : { color: "var(--nav-link-color)" }
            }
          >
            REPORTS
          </NavLink>
        </div>

        <div className="flex items-center space-x-4 text-sm font-mono">
          <label className="flex items-center space-x-2 text-[var(--nav-link-color)]">
            <span className="text-[10px] tracking-widest uppercase hidden sm:inline">Mode</span>
            <select
              value={mode}
              disabled={modeLoading}
              onChange={(e) => setMode(e.target.value)}
              className="bg-[var(--surface-card)] border border-[var(--border-color)] text-[var(--text-primary)] text-[11px] tracking-wider px-2 py-1.5 focus:outline-none focus:border-[var(--primary-accent)]"
            >
              {(modes.length
                ? modes
                : [
                    { id: "aws", label: "AWS Mode" },
                    { id: "local", label: "Local Mode" },
                  ]
              ).map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label || option.id}
                </option>
              ))}
            </select>
          </label>
          <span className="hidden lg:block text-[var(--nav-link-color)] text-[12px] tracking-wider">
            {user?.email || "Guest"}
          </span>
          <button
            onClick={handleLogout}
            className="px-4 py-1.5 border border-[var(--border-color)] text-[12px] tracking-wider text-[var(--nav-link-color)] bg-[var(--surface-card)] rounded-sm"
          >
            LOGOUT
          </button>
        </div>
      </nav>

      <main className="flex-1 max-w-[1280px] mx-auto px-6 w-full">
        <Outlet />
      </main>
    </div>
  );
}
