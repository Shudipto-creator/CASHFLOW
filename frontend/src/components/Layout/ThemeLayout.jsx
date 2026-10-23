import React, { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useMode } from "../../context/ModeContext";

export default function ThemeLayout() {
  const [isDark, setIsDark] = useState(true);
  const { user, logout } = useAuth();
  const { mode, modes, setMode, loading: modeLoading, local } = useMode();
  const navigate = useNavigate();

  // Update favicon based on theme
  const updateFavicon = (isDarkMode) => {
    const favicon = document.getElementById("favicon");
    if (favicon) {
      favicon.href = isDarkMode ? "/favicon-dark.svg" : "/favicon-light.svg";
    }
  };

  // Initialize theme from localStorage on component mount
  useEffect(() => {
    const savedTheme = localStorage.getItem("cfone-theme");
    if (savedTheme === "light") {
      setIsDark(false);
      document.documentElement.classList.add("light");
      updateFavicon(false);
    } else {
      setIsDark(true);
      document.documentElement.classList.remove("light");
      updateFavicon(true);
    }
  }, []);

  const toggleTheme = () => {
    if (isDark) {
      document.documentElement.classList.add("light");
      localStorage.setItem("cfone-theme", "light");
      setIsDark(false);
      updateFavicon(false);
    } else {
      document.documentElement.classList.remove("light");
      localStorage.setItem("cfone-theme", "dark");
      setIsDark(true);
      updateFavicon(true);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen relative overflow-x-hidden pb-4">
      <div className="scanlines"></div>
      <div className="vignette"></div>

      {/* Nav */}
      <nav
        className="sticky top-0 z-[90] h-14 flex items-center justify-between px-6 border-b"
        style={{
          backgroundColor: "var(--nav-bg)",
          borderColor: "var(--nav-border)",
        }}
      >
        <div className="flex items-center space-x-4">
          <div
            className="w-8 h-8 flex items-center justify-center font-mono font-bold text-base"
            style={{
              border: "1px solid var(--primary-accent)",
              color: "var(--primary-accent)",
              backgroundColor: "var(--surface-card)",
            }}
          >
            C
          </div>
          <span
            className="font-bold tracking-widest text-xl font-body"
            style={{ color: "var(--text-primary)" }}
          >
            CFONE
          </span>
        </div>

        <div className="hidden md:flex flex-1 justify-center space-x-2 font-mono text-[12px] tracking-wider">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? {
                    backgroundColor: "var(--surface-card)",
                    color: "var(--primary-accent)",
                  }
                : { color: "var(--nav-link-color)" }
            }
          >
            DASHBOARD
          </NavLink>
          <NavLink
            to="/documents"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? {
                    backgroundColor: "var(--surface-card)",
                    color: "var(--primary-accent)",
                  }
                : { color: "var(--nav-link-color)" }
            }
          >
            DOCUMENTS
          </NavLink>
          <NavLink
            to="/analysis"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? {
                    backgroundColor: "var(--surface-card)",
                    color: "var(--primary-accent)",
                  }
                : { color: "var(--nav-link-color)" }
            }
          >
            ANALYSIS
          </NavLink>
          <NavLink
            to="/reports"
            className={({ isActive }) =>
              `px-5 py-2.5 transition-colors ${isActive ? "shadow-sm rounded-sm" : ""}`
            }
            style={({ isActive }) =>
              isActive
                ? {
                    backgroundColor: "var(--surface-card)",
                    color: "var(--primary-accent)",
                  }
                : { color: "var(--nav-link-color)" }
            }
          >
            REPORTS
          </NavLink>
        </div>

        <div className="flex items-center space-x-6 text-sm font-mono">
          <label className="flex items-center space-x-2 text-[var(--nav-link-color)]">
            <span className="text-[10px] tracking-widest uppercase hidden sm:inline">Mode</span>
            <select
              value={mode}
              disabled={modeLoading}
              onChange={(e) => setMode(e.target.value)}
              title={
                mode === "local"
                  ? local?.chat_ready === false
                    ? "Local analysis ready; start Ollama for chat"
                    : "Local sklearn + Ollama"
                  : "AWS Bedrock Nova pipeline"
              }
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
            className="px-4 py-1.5 border border-[var(--border-color)] hover:border-[var(--primary-accent)] transition-colors text-[12px] tracking-wider text-[var(--nav-link-color)] bg-[var(--surface-card)]"
          >
            LOGOUT
          </button>
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-full bg-[var(--surface-card)] hover:scale-105 transition-transform"
            style={{ color: "var(--nav-link-color)" }}
          >
            {isDark ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </nav>

      <main className="max-w-[1280px] mx-auto px-6 mt-5 relative z-10 w-full">
        <Outlet />
      </main>
    </div>
  );
}
