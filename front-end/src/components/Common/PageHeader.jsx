import React from "react";

export default function PageHeader({ eyebrow, title, description, actions, children }) {
  return (
    <div className="mb-6 flex flex-col gap-4 border-b border-[var(--border-color)] pb-6 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-[var(--primary-accent)]">
            <span aria-hidden="true" className="h-1.5 w-1.5 bg-[var(--primary-accent)]" />
            {eyebrow}
          </p>
        )}
        <h1 className="text-5xl leading-none text-[var(--text-primary)] md:text-6xl">{title}</h1>
        {description && (
          <p className="mt-3 text-xs uppercase tracking-[0.15em] text-[var(--text-muted)]">{description}</p>
        )}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}
