"use server";

import { redirect } from "next/navigation";
import { login, getSession, dashboardPath } from "@/lib/auth";

export interface LoginState {
  error?: string;
}

export async function loginAction(_prevState: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");

  if (!email || !password) {
    return { error: "Enter your email and password." };
  }

  const result = await login(email, password);
  if (!result.ok) {
    return { error: result.error };
  }

  const session = await getSession();
  redirect(dashboardPath(session!.role));
}
