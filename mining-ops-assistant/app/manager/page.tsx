import { requireRole } from "@/lib/auth";
import { listAllReports } from "@/lib/db";
import { findRecurringEquipmentIssues } from "@/lib/insights";
import { NavBar } from "@/app/components/NavBar";
import { ReportsExplorer } from "./ReportsExplorer";

export default async function ManagerPage() {
  const session = await requireRole("manager");
  const reports = listAllReports();
  const recurring = findRecurringEquipmentIssues(reports);

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <NavBar name={session.name} role={session.role} />
      <main className="mx-auto w-full max-w-4xl flex-1 space-y-6 px-4 py-6">
        <div>
          <h1 className="text-lg font-semibold text-stone-900">Manager dashboard</h1>
          <p className="text-sm text-stone-600">
            {reports.length} shift report{reports.length === 1 ? "" : "s"} on file.
          </p>
        </div>

        {recurring.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-semibold text-red-800">Recurring equipment issues (last 14 days)</p>
            <ul className="mt-2 space-y-1 text-sm text-red-700">
              {recurring.map((r) => (
                <li key={r.equipment}>
                  {r.equipment} — {r.count} breakdowns reported
                </li>
              ))}
            </ul>
          </div>
        )}

        <ReportsExplorer reports={reports} />
      </main>
    </div>
  );
}
