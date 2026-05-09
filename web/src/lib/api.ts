import type { ScannerState } from './types';

const BASE = '';

export async function fetchScannerState(): Promise<ScannerState> {
  const res = await fetch(`${BASE}/api/scanner_state`);
  if (!res.ok) throw new Error(`scanner_state: ${res.status}`);
  return res.json() as Promise<ScannerState>;
}
