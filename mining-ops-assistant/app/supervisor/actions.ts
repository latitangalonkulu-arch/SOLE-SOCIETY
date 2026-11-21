"use server";

import { requireRole } from "@/lib/auth";
import { parseShiftUpdate } from "@/lib/parser";
import { addReport } from "@/lib/db";
import type { ParsedReport, Shift } from "@/lib/types";

export async function previewReportAction(
  rawUpdate: string
): Promise<{ ok: true; draft: ParsedReport } | { ok: false; error: string }> {
  await requireRole("supervisor");

  const trimmed = rawUpdate.trim();
  if (trimmed.length < 10) {
    return { ok: false, error: "Add a few more details before generating the report." };
  }

  return { ok: true, draft: parseShiftUpdate(trimmed) };
}

export interface SubmitReportInput {
  shift: Shift;
  section: string;
  rawUpdate: string;
  production: string;
  equipment: string[];
  safety: string;
  staffing: string;
  flags: string[];
}

export async function submitReportAction(
  input: SubmitReportInput
): Promise<{ ok: true } | { ok: false; error: string }> {
  const session = await requireRole("supervisor");

  const rawUpdate = input.rawUpdate.trim();
  const production = input.production.trim();
  if (!rawUpdate || !production) {
    return { ok: false, error: "The raw update and production summary can't be empty." };
  }

  addReport({
    supervisorId: session.uid,
    supervisorName: session.name,
    shift: input.shift,
    section: input.section.trim() || session.section || "Unassigned",
    rawUpdate,
    production,
    equipment: input.equipment.map((e) => e.trim()).filter(Boolean),
    safety: input.safety.trim() || "No safety incidents reported.",
    staffing: input.staffing.trim() || "Full crew.",
    flags: input.flags.map((f) => f.trim()).filter(Boolean),
  });

  return { ok: true };
}
