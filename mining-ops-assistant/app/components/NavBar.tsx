import { logoutAction } from "@/app/actions/auth";
import type { Role } from "@/lib/types";

export function NavBar({
  name,
  role,
  section,
}: {
  name: string;
  role: Role;
  section?: string;
}) {
  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-stone-900">Dlamini Ridge Mining</p>
          <p className="text-xs text-stone-500">AI Operations Assistant — pilot demo</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right text-sm">
            <p className="font-medium text-stone-900">{name}</p>
            <p className="text-xs text-stone-500">
              {role === "manager" ? "Manager" : `Supervisor${section ? ` — ${section}` : ""}`}
            </p>
          </div>
          <form action={logoutAction}>
            <button
              type="submit"
              className="rounded-md border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50"
            >
              Log out
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
