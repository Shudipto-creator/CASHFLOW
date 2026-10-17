/* CASHFLOW app.js - UI behaviour. No globals. */

const APP = (() => {
  const sidebar = document.getElementById("app-sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  const mobileMenu = document.getElementById("mobile-menu");
  const backdrop = document.getElementById("drawer-backdrop");

  function saveCollapsed(collapsed) {
    try {
      localStorage.setItem("cf_sidebar_collapsed", String(collapsed));
    } catch (_) {
      // localStorage unavailable; ignore
    }
  }

  function initSidebar() {
    if (!sidebar || !toggle) return;
    try {
      const stored = localStorage.getItem("cf_sidebar_collapsed");
      if (stored === "true") sidebar.classList.add("collapsed");
    } catch (_) {}
    toggle.addEventListener("click", () => {
      const collapsed = !sidebar.classList.contains("collapsed");
      sidebar.classList.toggle("collapsed");
      saveCollapsed(collapsed);
    });
  }

  function initMobileMenu() {
    if (!mobileMenu || !backdrop || !sidebar) return;
    function openMenu() {
      sidebar.classList.add("open");
      backdrop.classList.add("open");
    }
    function closeMenu() {
      sidebar.classList.remove("open");
      backdrop.classList.remove("open");
    }
    mobileMenu.addEventListener("click", openMenu);
    backdrop.addEventListener("click", closeMenu);
  }

  function initDialogs() {
    document.querySelectorAll("dialog").forEach((dialog) => {
      const openBtn = document.querySelector(`[data-dialog="${dialog.id}"]`);
      const closeBtns = dialog.querySelectorAll("[data-close], .dialog-close");
      if (openBtn) {
        openBtn.addEventListener("click", (e) => {
          e.preventDefault();
          dialog.showModal();
        });
      }
      closeBtns.forEach((btn) => {
        btn.addEventListener("click", () => dialog.close());
      });
      dialog.addEventListener("click", (e) => {
        if (e.target === dialog) dialog.close();
      });
    });
  }

  function initSubmitLock() {
    document.querySelectorAll("form[data-lock]").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btns = form.querySelectorAll("button[type=submit]");
        btns.forEach((b) => { b.disabled = true; });
        const formData = new FormData(form);
        const body = {};
        for (const [key, value] of formData.entries()) {
          body[key] = value;
        }
        try {
          const res = await fetch(form.action, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            credentials: "include",
          });
          if (res.ok) {
            window.location.href = "/app";
          } else {
            const err = await res.json().catch(() => ({ detail: "Login failed" }));
            const msg = err.detail || "Login failed";
            const existing = form.querySelector(".form-error");
            if (existing) existing.remove();
            const p = document.createElement("p");
            p.className = "form-error";
            p.style.color = "var(--color-danger)";
            p.style.fontSize = "var(--text-12)";
            p.style.marginTop = "var(--space-6)";
            p.textContent = msg;
            form.appendChild(p);
            btns.forEach((b) => { b.disabled = false; });
          }
        } catch (_) {
          btns.forEach((b) => { b.disabled = false; });
        }
      });
    });
  }

  function initConfirms() {
    document.querySelectorAll("[data-confirm]").forEach((el) => {
      el.addEventListener("click", (e) => {
        const message = el.getAttribute("data-confirm");
        if (!confirm(message)) e.preventDefault();
      });
    });
  }

  function initTheme() {
    const btn = document.getElementById("theme-toggle");
    const html = document.documentElement;
    if (!btn) return;
    function apply(theme) {
      html.setAttribute("data-theme", theme);
      try { localStorage.setItem("cf_theme", theme); } catch (_) {}
      if (typeof window.dispatchEvent === "function") {
        window.dispatchEvent(new Event("cf:themechange"));
      }
    }
    try {
      const stored = localStorage.getItem("cf_theme");
      if (stored) apply(stored);
    } catch (_) {}
    btn.addEventListener("click", () => {
      const current = html.getAttribute("data-theme") || "light";
      const next = current === "dark" ? "light" : "dark";
      apply(next);
    });
  }

  return { init: () => { initSidebar(); initMobileMenu(); initDialogs(); initSubmitLock(); initConfirms(); initTheme(); } };
})();

document.addEventListener("DOMContentLoaded", () => APP.init());
