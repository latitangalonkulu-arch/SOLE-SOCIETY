import { redirect } from "next/navigation";
import { getSession, dashboardPath } from "@/lib/auth";
import { LoginForm } from "./LoginForm";

export default async function LoginPage() {
  const session = await getSession();
  if (session) redirect(dashboardPath(session.role));

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-stone-900">Dlamini Ridge Mining</h1>
        <p className="mt-1 text-sm text-stone-600">AI Operations Assistant — pilot demo</p>
      </div>
      <LoginForm />
    </div>
  );
}
