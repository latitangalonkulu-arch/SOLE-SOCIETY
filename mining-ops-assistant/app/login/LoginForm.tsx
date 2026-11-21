"use client";

import { useActionState } from "react";
import { loginAction, type LoginState } from "./actions";

const initialState: LoginState = {};

const DEMO_ACCOUNTS = [
  { label: "Manager", email: "manager@dlaminiridge.co.za" },
  { label: "Supervisor — Section 4", email: "thabo@dlaminiridge.co.za" },
  { label: "Supervisor — Section 7", email: "nomvula@dlaminiridge.co.za" },
];

export function LoginForm() {
  const [state, formAction, pending] = useActionState(loginAction, initialState);

  return (
    <div className="w-full max-w-sm">
      <form
        action={formAction}
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm space-y-4"
      >
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-stone-700">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoFocus
            className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
            placeholder="you@dlaminiridge.co.za"
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-stone-700">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
            placeholder="••••••••"
          />
        </div>
        {state.error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{state.error}</p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-md bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-60"
        >
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <div className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-4 text-xs text-stone-600">
        <p className="font-semibold text-stone-700">Demo accounts (password: pilot2024)</p>
        <ul className="mt-2 space-y-1">
          {DEMO_ACCOUNTS.map((a) => (
            <li key={a.email} className="flex justify-between gap-2">
              <span>{a.label}</span>
              <span className="font-mono">{a.email}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
