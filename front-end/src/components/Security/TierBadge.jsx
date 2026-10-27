import React from 'react';
import { Shield, ShieldAlert, ShieldCheck } from 'lucide-react';

const TIER_CONFIG = {
  green: {
    label: 'Green',
    icon: ShieldCheck,
    tone: 'text-[var(--positive-color)]',
    border: 'border-[var(--positive-color)]/30',
    bg: 'bg-[var(--positive-color)]/10',
  },
  yellow: {
    label: 'Yellow',
    icon: ShieldAlert,
    tone: 'text-[#d97706]',
    border: 'border-[#d97706]/30',
    bg: 'bg-[#d97706]/10',
  },
  red: {
    label: 'Red',
    icon: ShieldAlert,
    tone: 'text-[var(--negative-color)]',
    border: 'border-[var(--negative-color)]/30',
    bg: 'bg-[var(--negative-color)]/10',
  },
};

export default function TierBadge({ tier }) {
  const config = TIER_CONFIG[tier] || TIER_CONFIG.green;
  const Icon = config.icon;
  return (
    <span className={`inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.15em] ${config.bg} ${config.border} ${config.tone}`}>
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {config.label} tier
    </span>
  );
}
