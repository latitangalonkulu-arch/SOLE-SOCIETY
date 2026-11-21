"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { previewReportAction, submitReportAction } from "./actions";
import type { ParsedReport, Shift } from "@/lib/types";

const EXAMPLE_UPDATE =
  "Day shift, Section 4. Truck 12 broke down at 10, hydraulic leak, back by 2. About 800 tons moved. One near miss. Short two people.";

function linesToArray(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export function ReportForm({ defaultSection }: { defaultSection: string }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const [shift, setShift] = useState<Shift>("Day");
  const [section, setSection] = useState(defaultSection);
  const [raw, setRaw] = useState("");
  const [draft, setDraft] = useState<ParsedReport | null>(null);

  const [production, setProduction] = useState("");
  const [equipmentText, setEquipmentText] = useState("");
  const [safety, setSafety] = useState("");
  const [staffing, setStaffing] = useState("");
  const [flagsText, setFlagsText] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function applyDraft(d: ParsedReport) {
    setDraft(d);
    setProduction(d.production);
    setEquipmentText(d.equipment.join("\n"));
    setSafety(d.safety);
    setStaffing(d.staffing);
    setFlagsText(d.flags.join("\n"));
  }

  function handleGenerate() {
    setError(null);
    setSuccess(null);
    startTransition(async () => {
      const result = await previewReportAction(raw);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      applyDraft(result.draft);
    });
  }

  function handleSubmit() {
    setError(null);
    startTransition(async () => {
      const result = await submitReportAction({
        shift,
        section,
        rawUpdate: raw,
        production,
        equipment: linesToArray(equipmentText),
        safety,
        staffing,
        flags: linesToArray(flagsText),
      });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSuccess("Report filed and sent to the manager.");
      setDraft(null);
      setRaw("");
      router.refresh();
    });
  }

  function handleStartOver() {
    setDraft(null);
    setSuccess(null);
    setError(null);
  }

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-stone-900">New shift report</h2>
        {!draft && (
          <button
            type="button"
            onClick={() => setRaw(EXAMPLE_UPDATE)}
            className="text-xs font-medium text-amber-700 hover:underline"
          >
            Use example update
          </button>
        )}
      </div>

      {!draft ? (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-stone-600">Shift</label>
              <select
                value={shift}
                onChange={(e) => setShift(e.target.value as Shift)}
                className="mt-1 w-full rounded-md border border-stone-300 px-2 py-1.5 text-sm"
              >
                <option value="Day">Day</option>
                <option value="Night">Night</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-600">Section</label>
              <input
                value={section}
                onChange={(e) => setSection(e.target.value)}
                className="mt-1 w-full rounded-md border border-stone-300 px-2 py-1.5 text-sm"
                placeholder="Section 4"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-stone-600">
              Quick update — type or paste what you&apos;d say in a voice note
            </label>
            <textarea
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              rows={5}
              className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
              placeholder={EXAMPLE_UPDATE}
            />
          </div>

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <button
            type="button"
            onClick={handleGenerate}
            disabled={pending || raw.trim().length === 0}
            className="rounded-md bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-60"
          >
            {pending ? "Generating…" : "Generate report"}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Draft generated from your update. Review and edit before filing — you always have the final say.
          </p>

          <Field label="Production" value={production} onChange={setProduction} />
          <Field
            label="Equipment (one item per line)"
            value={equipmentText}
            onChange={setEquipmentText}
            multiline
          />
          <Field label="Safety" value={safety} onChange={setSafety} multiline />
          <Field label="Staffing" value={staffing} onChange={setStaffing} />
          <Field
            label="Flag for manager (one item per line, leave blank if none)"
            value={flagsText}
            onChange={setFlagsText}
            multiline
          />

          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={pending}
              className="rounded-md bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-60"
            >
              {pending ? "Submitting…" : "Submit to manager"}
            </button>
            <button
              type="button"
              onClick={handleStartOver}
              disabled={pending}
              className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
            >
              Edit raw update
            </button>
          </div>
        </div>
      )}

      {success && (
        <p className="mt-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">{success}</p>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-stone-600">{label}</label>
      {multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
        />
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-1 w-full rounded-md border border-stone-300 px-3 py-2 text-sm focus:border-amber-600 focus:outline-none focus:ring-1 focus:ring-amber-600"
        />
      )}
    </div>
  );
}
