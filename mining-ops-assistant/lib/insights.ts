import type { ShiftReport } from "./types";

export interface RecurringIssue {
  equipment: string;
  count: number;
  reportIds: string[];
}

const RECENT_DAYS = 14;

// Flags equipment that shows up "down" in two or more reports within the
// recent window — the proposal's "catches repeat problems early" benefit.
export function findRecurringEquipmentIssues(reports: ShiftReport[]): RecurringIssue[] {
  const cutoff = Date.now() - RECENT_DAYS * 24 * 60 * 60 * 1000;
  const counts = new Map<string, { count: number; reportIds: string[] }>();

  for (const report of reports) {
    if (new Date(report.createdAt).getTime() < cutoff) continue;
    for (const line of report.equipment) {
      const m = line.match(/^([A-Za-z]+\s+\d+)\s+down/i);
      if (!m) continue;
      const key = m[1];
      const entry = counts.get(key) ?? { count: 0, reportIds: [] };
      entry.count += 1;
      entry.reportIds.push(report.id);
      counts.set(key, entry);
    }
  }

  return Array.from(counts.entries())
    .filter(([, v]) => v.count >= 2)
    .map(([equipment, v]) => ({ equipment, count: v.count, reportIds: v.reportIds }))
    .sort((a, b) => b.count - a.count);
}
