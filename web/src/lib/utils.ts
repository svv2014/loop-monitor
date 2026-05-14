import { useState, useEffect } from 'react';

/** Parses a UTC ISO string that may lack a Z/offset suffix (e.g. from SQLite). */
export function parseServerTs(s: string): number {
  if (!s) return NaN;
  // If the string already has a timezone indicator, parse as-is; otherwise treat as UTC.
  const normalized = /[Zz]$|[+-]\d{2}:\d{2}$/.test(s) ? s : s + 'Z';
  return new Date(normalized).getTime();
}

export function relTime(ts: number): string {
  if (!isFinite(ts)) return '—';
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return s + 's ago';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}

export function absoluteUtc(tsMs: number): string {
  return new Date(tsMs).toISOString();
}

export function durationFmt(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return s + 's';
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return `${m}m ${String(r).padStart(2, '0')}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function matchesProjectFilter(project: string, filter: string | null | undefined): boolean {
  return !filter || project === filter;
}

export function useTick(ms = 1000): void {
  const [, setN] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setN(n => n + 1), ms);
    return () => clearInterval(id);
  }, [ms]);
}
