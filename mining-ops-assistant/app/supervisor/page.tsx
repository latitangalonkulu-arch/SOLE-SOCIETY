import { requireRole } from "@/lib/auth";
import { listReportsBySupervisor } from "@/lib/db";
import { NavBar } from "@/app/components/NavBar";
import { ReportCard } from "@/app/components/ReportCard";
import { ReportForm } from "./ReportForm";

export default async function SupervisorPage() {
  const session = await requireRole("supervisor");
  const reports = listReportsBySupervisor(session.uid);

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <NavBar name={session.name} role={session.role} section={session.section} />
      <main className="mx-auto w-full max-w-3xl flex-1 space-y-6 px-4 py-6">
        <ReportForm defaultSection={session.section || ""} />

        <section>
          <h2 className="text-sm font-semibold text-stone-900">Your recent reports</h2>
          <div className="mt-3 space-y-3">
            {reports.length === 0 && (
              <p className="text-sm text-stone-500">No reports filed yet.</p>
            )}
            {reports.map((r) => (
              <ReportCard key={r.id} report={r} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
