import type { ShiftReport } from "@/lib/types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ReportCard({ report, showSupervisor }: { report: ShiftReport; showSupervisor?: boolean }) {
  const flagged = report.flags.length > 0;

  return (
    <article
      className={`rounded-xl border bg-white p-4 shadow-sm ${flagged ? "border-amber-300" : "border-stone-200"}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-stone-900">
          <span>
            {report.shift} shift — {report.section}
          </span>
          {flagged && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Flagged
            </span>
          )}
        </div>
        <span className="text-xs text-stone-500">{formatDate(report.createdAt)}</span>
      </div>
      {showSupervisor && (
        <p className="mt-1 text-xs text-stone-500">Filed by {report.supervisorName}</p>
      )}

      <dl className="mt-3 space-y-2 text-sm">
        <Row label="Production" value={report.production} />
        {report.equipment.length > 0 && (
          <Row label="Equipment" value={report.equipment.join(" ")} />
        )}
        <Row label="Safety" value={report.safety} />
        <Row label="Staffing" value={report.staffing} />
      </dl>

      {flagged && (
        <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <p className="font-semibold">Flag for manager</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {report.flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="mt-3 text-xs text-stone-500">
        <summary className="cursor-pointer select-none">Original update</summary>
        <p className="mt-1 whitespace-pre-wrap">{report.rawUpdate}</p>
      </details>
    </article>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-stone-400">{label}</dt>
      <dd className="text-stone-800">{value}</dd>
    </div>
  );
}
