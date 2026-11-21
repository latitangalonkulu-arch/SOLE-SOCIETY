import "server-only";
import crypto from "node:crypto";
import bcrypt from "bcryptjs";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getUserByEmail } from "./db";
import type { Role, SessionPayload } from "./types";

const COOKIE_NAME = "dr_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 7; // 7 days

// Baked-in fallback so the demo runs with zero setup. Set AUTH_SECRET in the
// environment before using this for anything beyond a local pilot demo.
const SECRET = process.env.AUTH_SECRET || "dlamini-ridge-pilot-demo-secret-change-me";

function base64url(input: Buffer): string {
  return input.toString("base64url");
}

function sign(payload: SessionPayload): string {
  const json = Buffer.from(JSON.stringify(payload), "utf-8");
  const body = base64url(json);
  const mac = crypto.createHmac("sha256", SECRET).update(body).digest();
  return `${body}.${base64url(mac)}`;
}

function verify(token: string): SessionPayload | null {
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [body, mac] = parts;
  const expectedMac = base64url(crypto.createHmac("sha256", SECRET).update(body).digest());
  if (mac.length !== expectedMac.length) return null;
  if (!crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(expectedMac))) return null;
  try {
    return JSON.parse(Buffer.from(body, "base64url").toString("utf-8")) as SessionPayload;
  } catch {
    return null;
  }
}

export async function login(
  email: string,
  password: string
): Promise<{ ok: true } | { ok: false; error: string }> {
  const user = getUserByEmail(email.trim());
  if (!user) return { ok: false, error: "No account found for that email." };
  const valid = bcrypt.compareSync(password, user.passwordHash);
  if (!valid) return { ok: false, error: "Incorrect password." };

  const payload: SessionPayload = {
    uid: user.id,
    name: user.name,
    role: user.role,
    section: user.section,
  };
  (await cookies()).set(COOKIE_NAME, sign(payload), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
    secure: process.env.NODE_ENV === "production",
  });
  return { ok: true };
}

export async function logout(): Promise<void> {
  (await cookies()).delete(COOKIE_NAME);
}

export async function getSession(): Promise<SessionPayload | null> {
  const token = (await cookies()).get(COOKIE_NAME)?.value;
  if (!token) return null;
  return verify(token);
}

function dashboardPathFor(role: Role): string {
  return role === "manager" ? "/manager" : "/supervisor";
}

export async function requireUser(): Promise<SessionPayload> {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

export async function requireRole(role: Role): Promise<SessionPayload> {
  const session = await requireUser();
  if (session.role !== role) redirect(dashboardPathFor(session.role));
  return session;
}

export function dashboardPath(role: Role): string {
  return dashboardPathFor(role);
}
