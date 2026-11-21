"use client";

import { useMemo, useState } from "react";
import type { ShiftReport } from "@/lib/types";
import { ReportCard } from "@/app/components/ReportCard";

function matchesQuery(report: ShiftReport, query: string): boolean {
  if (!query) return true;
  const haystack = [
    report.supervisorName,
    report.section,
    report.shift,
    report.rawUpdate,
    report.production,
    report.equipment.join(" "),
    report.safety,
    report.staffing,
    report.flags.join(" "),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

export function ReportsExplorer({ reports }: { reports: ShiftReport[] }) {
  const [query, setQuery] = useState("");
  const [section, setSection] = useState("All sections");
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  const sections = useMemo(
    () => ["All sections", ...Array.from(new Set(reports.map((r) => r.section))).sort()],
    [reports]
  );

  const filtered = reports.filter((r) => {
    if (section !== "All sections" && r.section !== section) return false;
    if (flaggedOnly && r.flags.length === 0) return false;
    return matchesQuery(r, query);
  });

  return (
    <section>
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search reports — e.g. Truck 12, near miss, Thabo…"
          className="min-w-[220px] flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
        />
        <select
          value={section}
          onChange={(e) => setSection(e.target.value)}
          className="rounded-md border border-stone-300 px-2 py-2 text-sm"
        >
          {sections.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-stone-700">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => setFlaggedOnly(e.target.checked)}
            className="rounded border-stone-300"
          />
          Flagged only
        </label>
      </div>

      <div className="mt-4 space-y-3">
        {filtered.length === 0 && (
          <p className="text-sm text-stone-500">No reports match your filters.</p>
        )}
        {filtered.map((r) => (
          <ReportCard key={r.id} report={r} showSupervisor />
        ))}
      </div>
    </section>
  );
}
