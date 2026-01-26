'use client';

import React from 'react';
import { cn } from '@/lib/utils';

export function FilterBtn({ active, onClick, label, variant }: { active: boolean, onClick: () => void, label: string, variant: string }) {
  const base = "px-4 py-2 text-[10px] font-bold uppercase tracking-wider rounded-full border border-white/5 transition-all";
  const styles = {
    all: active ? 'bg-white/20 text-white' : 'bg-white/5 text-slate-400 hover:bg-white/10',
    pending: active ? 'bg-amber-500/40 text-amber-200' : 'bg-amber-500/10 text-amber-400 hover:bg-amber-500/20',
    accepted: active ? 'bg-green-500/40 text-green-200' : 'bg-green-500/10 text-green-400 hover:bg-green-500/20',
    rejected: active ? 'bg-red-500/40 text-red-200' : 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
  };
  return <button onClick={onClick} className={cn(base, styles[variant as keyof typeof styles])}>{label}</button>;
}