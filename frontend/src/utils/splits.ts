export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
export const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'];

export function isoWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil(((d.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

/** Year-agnostic week keys W01..W52, plus W53 for years that have 53 ISO weeks. */
export function weekKeys(year: number): string[] {
  const count = isoWeekNumber(new Date(year, 11, 28)); // Dec 28 is always in the last ISO week
  return Array.from({ length: count }, (_, i) => `W${String(i + 1).padStart(2, '0')}`);
}

export function periodKeysFor(logic: string, year: number): string[] {
  if (logic === 'Month') return MONTHS;
  if (logic === 'Quarter') return QUARTERS;
  if (logic === 'Week') return weekKeys(year);
  return [];
}

/** Converts legacy week keys ("2026-W05", "W5") to "W05" so old templates load into the editor. */
export function normalizeWeightKeys(logic: string, values: Record<string, number>): Record<string, number> {
  if (logic !== 'Week') return values;
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(values)) {
    const m = /^(?:\d{4}-)?W(\d{1,2})$/i.exec(key.trim());
    if (!m) continue;
    const k = `W${m[1].padStart(2, '0')}`;
    out[k] = (out[k] ?? 0) + Number(value);
  }
  return out;
}

export function weightsTotal(values: Record<string, string>): number {
  return Object.values(values).reduce((sum, v) => {
    const n = Number(v);
    return sum + (v.trim() !== '' && Number.isFinite(n) ? n : 0);
  }, 0);
}

/** Text inputs -> numeric weights. Blank boxes count as 0; returns an error message if invalid. */
export function parseWeights(values: Record<string, string>, keys: string[]): Record<string, number> | string {
  const out: Record<string, number> = {};
  for (const key of keys) {
    const raw = (values[key] ?? '').trim();
    const n = raw === '' ? 0 : Number(raw);
    if (!Number.isFinite(n) || n < 0) return `Weight for ${key} must be a number of 0 or more.`;
    out[key] = n;
  }
  if (Object.values(out).every((v) => v === 0)) return 'Enter at least one weight above 0.';
  return out;
}
