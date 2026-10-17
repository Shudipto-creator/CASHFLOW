import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Menu, X } from 'lucide-react';

const groups = [
  { title: 'Overview', items: [
    { to: '/app', label: 'Dashboard', end: true },
    { to: '/app/ask', label: 'Ask CASHFLOW' },
    { to: '/app/scenarios', label: 'Scenarios' },
    { to: '/app/alerts', label: 'Alerts' },
  ]},
  { title: 'Money', items: [
    { to: '/app/financing', label: 'Financing' },
    { to: '/app/approvals', label: 'Approvals', badge: 'pendingApprovals' },
    { to: '/app/accounts', label: 'Accounts' },
    { to: '/app/transactions', label: 'Transactions' },
    { to: '/app/documents', label: 'Documents' },
    { to: '/app/goals', label: 'Goals' },
  ]},
  { title: 'Trust', items: [
    { to: '/app/audit', label: 'Audit log' },
    { to: '/app/settings', label: 'Settings' },
  ]},
];

export default function ThemeLayout() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    const pref = localStorage.getItem('theme');
    const isDark = pref === 'dark' || (pref === null && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', isDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  }, []);

  const toggleTheme = () => {
    const isDark = document.documentElement.classList.contains('dark');
    document.documentElement.classList.toggle('dark', !isDark);
    document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
  };

  const sidebar = (
    <aside
      className="flex flex-col h-full bg-surface border-r border-border"
      style={{ width: collapsed ? 64 : 240, transition: 'color 120ms, background 120ms' }}
    >
      <div className="flex items-center justify-between p-4 border-b border-border">
        <span className="font-serif tracking-[0.08em] font-semibold" style={{ fontSize: 16 }}>CASHFLOW</span>
        <button className="btn btn-ghost" onClick={() => setCollapsed(!collapsed)} aria-label="collapse sidebar">
          {collapsed ? '>' : '<'}
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2" aria-label="main">
        {groups.map((g) => (
          <div key={g.title} className="mb-4">
            {!collapsed && <div className="text-muted text-xs px-2 py-1 uppercase">{g.title}</div>}
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                className={({ isActive }) =>
                  'flex items-center justify-between px-2 py-2 rounded-md text-sm ' +
                  (isActive ? 'bg-primary text-bg' : 'hover:bg-surface')
                }
              >
                {!collapsed && <span>{it.label}</span>}
                {it.badge === 'pendingApprovals' && pendingCount > 0 && (
                  <span className="tag" style={{ background: 'var(--color-danger)', color: '#ffffff' }}>{pendingCount}</span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <div className="border-t border-border p-3">
        {!collapsed && (
          <div className="text-sm">
            <div className="font-semibold">{user?.first_name || user?.email}</div>
            {user?.organization_id && <div className="text-xs text-muted">Organization</div>}
          </div>
        )}
        <button className="btn btn-ghost w-full mt-2" onClick={toggleTheme} aria-label="toggle theme">
          {collapsed ? 'T' : 'Toggle theme'}
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen" style={{ background: 'var(--color-bg)' }}>
      <button className="btn btn-ghost lg:hidden" style={{ position: 'absolute', top: 12, left: 12, zIndex: 50 }} onClick={() => setMobileOpen(true)}>
        Menu
      </button>
      <div className="hidden lg:block">{sidebar}</div>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div className="relative">{sidebar}</div>
        </div>
      )}
      <main className="flex-1 overflow-y-auto" style={{ maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </main>
    </div>
  );
}
