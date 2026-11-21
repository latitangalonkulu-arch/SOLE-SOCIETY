import type { ParsedReport } from "./types";

// A rule-based reader for free-text shift updates. It is deliberately simple
// (keyword + regex matching, no model call) so the demo needs no API key.
// A supervisor always reviews and can edit every field before filing, so the
// bar for this first pass is "a good, fast draft" rather than perfect
// extraction. Swap this module for a Claude API call later without touching
// the rest of the app — see README's "Upgrade path" section.

const EQUIPMENT_WORDS = [
  "truck",
  "loader",
  "excavator",
  "drill",
  "dozer",
  "bulldozer",
  "grader",
  "crusher",
  "conveyor",
  "pump",
  "shovel",
  "ripper",
];

const SAFETY_KEYWORDS = [
  "near miss",
  "near-miss",
  "injury",
  "injured",
  "incident",
  "unsafe",
  "ppe",
  "accident",
  "hazard",
];

const STAFFING_KEYWORDS = [
  "short",
  "absent",
  "no-show",
  "noshow",
  "understaffed",
  "short-staffed",
  "short staffed",
];

const PRODUCTION_KEYWORDS = [
  "ton",
  "tonne",
  "load",
  "moved",
  "hauled",
  "produced",
  "mined",
  "extracted",
];

const RESOLVED_KEYWORDS = ["back", "repair", "fixed", "operational", "running", "resolved"];
const DOWN_KEYWORDS = ["broke", "break", "down", "fault", "fail", "leak", "stopped", "stuck"];

const REASON_PHRASES = [
  "hydraulic leak",
  "electrical fault",
  "flat tyre",
  "flat tire",
  "engine failure",
  "overheating",
  "brake failure",
  "transmission issue",
  "belt slipped",
  "fuel issue",
  "oil leak",
];

const NUMBER_WORDS: Record<string, number> = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
};
const WORDS_BY_NUMBER: Record<number, string> = Object.fromEntries(
  Object.entries(NUMBER_WORDS).map(([w, n]) => [n, w])
);

function wordToNumber(w: string | undefined): number | null {
  if (!w) return null;
  const lw = w.toLowerCase();
  if (NUMBER_WORDS[lw] !== undefined) return NUMBER_WORDS[lw];
  const n = parseInt(w, 10);
  return Number.isNaN(n) ? null : n;
}

function numberToWord(n: number): string {
  return WORDS_BY_NUMBER[n] || String(n);
}

function splitSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function capitalize(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

type Category = "equipment" | "safety" | "staffing" | "production" | "other";

function classify(sentence: string): Category {
  const s = sentence.toLowerCase();
  if (SAFETY_KEYWORDS.some((k) => s.includes(k))) return "safety";
  if (EQUIPMENT_WORDS.some((k) => new RegExp(`\\b${k}\\b`).test(s))) return "equipment";
  if (STAFFING_KEYWORDS.some((k) => s.includes(k))) return "staffing";
  if (PRODUCTION_KEYWORDS.some((k) => s.includes(k))) return "production";
  return "other";
}

function parseProduction(sentences: string[]): string {
  for (const s of sentences) {
    const m = s.match(/(\d[\d,.]*)\s*(tons?|tonnes?|loads?)/i);
    if (m) {
      const unit = /ton/i.test(m[2]) ? "tons" : "loads";
      return `Approximately ${m[1]} ${unit} moved.`;
    }
  }
  if (sentences.length) return capitalize(sentences.join(". ")) + ".";
  return "No production figures reported — confirm tonnage with supervisor.";
}

function parseTime(sentence: string): string | null {
  const startM = sentence.match(/\bat\s+(\d{1,2})(?::(\d{2}))?\b/i);
  const endM = sentence.match(/\bby\s+(\d{1,2})(?::(\d{2}))?\b/i);
  if (!startM) return null;
  const start = parseInt(startM[1], 10);
  const startMin = startM[2] || "00";
  let end = endM ? parseInt(endM[1], 10) : null;
  const endMin = endM && endM[2] ? endM[2] : "00";
  if (end !== null && end <= start) end += 12;
  const fmt = (h: number, m: string) => `${String(h).padStart(2, "0")}:${m}`;
  if (end !== null) return `${fmt(start, startMin)} to ${fmt(end, endMin)}`;
  return fmt(start, startMin);
}

interface EquipmentItem {
  text: string;
  name: string;
  id: string;
  isDown: boolean;
  reasonWord: string | null;
}

function parseEquipment(sentences: string[]): EquipmentItem[] {
  const items: EquipmentItem[] = [];
  for (const s of sentences) {
    for (const word of EQUIPMENT_WORDS) {
      const re = new RegExp(`\\b(${word})\\s*#?(\\d+)\\b`, "i");
      const m = s.match(re);
      if (m) {
        const name = capitalize(m[1]);
        const id = m[2];
        const lower = s.toLowerCase();
        const isDown = DOWN_KEYWORDS.some((k) => lower.includes(k));
        const isResolved = RESOLVED_KEYWORDS.some((k) => lower.includes(k));
        const reason = REASON_PHRASES.find((p) => lower.includes(p));
        const timeRange = parseTime(s);
        let text: string;
        if (isDown) {
          text = `${name} ${id} down`;
          if (timeRange) text += ` ${timeRange}`;
          if (reason) text += `, ${reason}`;
          text += isResolved ? ", repaired." : ", repair in progress.";
        } else {
          text = `${name} ${id} operational.`;
        }
        items.push({ text, name, id, isDown, reasonWord: reason ? reason.split(" ")[0] : null });
        break;
      }
    }
  }
  return items;
}

function parseSafety(sentences: string[]): string {
  if (!sentences.length) return "No safety incidents reported.";
  const parts: string[] = [];
  for (const s of sentences) {
    const lower = s.toLowerCase();
    if (
      /\bno\b[^.]*(incident|issue|near miss|injury|hazard)/.test(lower) ||
      /\b(clear|clean|quiet) shift\b/.test(lower)
    ) {
      parts.push("No safety incidents reported.");
      continue;
    }
    const countMatch = s.match(/\b(one|two|three|four|five|\d+)\b/i);
    const count = countMatch ? wordToNumber(countMatch[1]) ?? 1 : 1;
    if (lower.includes("near miss") || lower.includes("near-miss")) {
      parts.push(
        `${capitalize(numberToWord(count))} near miss${count > 1 ? "es" : ""} reported. Follow-up recommended.`
      );
    } else {
      parts.push(capitalize(s) + ".");
    }
  }
  return parts.join(" ");
}

function parseStaffing(sentences: string[]): string {
  if (!sentences.length) return "Full crew.";
  for (const s of sentences) {
    const m = s.match(/short\s+(\w+)/i);
    if (m) {
      const n = wordToNumber(m[1]);
      if (n) return `${capitalize(numberToWord(n))} ${n === 1 ? "person" : "people"} short.`;
    }
  }
  return capitalize(sentences.join(". ")) + ".";
}

function buildFlags(args: {
  equipmentItems: EquipmentItem[];
  safetyText: string;
  staffingText: string;
}): string[] {
  const { equipmentItems, safetyText, staffingText } = args;
  const flags: string[] = [];
  for (const item of equipmentItems) {
    if (item.isDown) {
      const descriptor = item.reasonWord ? `${item.reasonWord} issue` : "issue";
      flags.push(`${item.name} ${item.id} ${descriptor} — check maintenance history.`);
    }
  }
  if (!/^no safety incidents/i.test(safetyText) && /near miss|injury|incident/i.test(safetyText)) {
    flags.push("Safety follow-up required.");
  }
  const staffWordMatch = staffingText.match(/^(\w+) (?:person|people) short/);
  const staffCount = staffWordMatch ? wordToNumber(staffWordMatch[1]) : null;
  if (staffCount && staffCount >= 2) {
    flags.push(`Short-staffed — ${numberToWord(staffCount)} short, monitor coverage.`);
  }
  return flags;
}

export function parseShiftUpdate(raw: string): ParsedReport {
  const sentences = splitSentences(raw);
  const buckets: Record<Category, string[]> = {
    equipment: [],
    safety: [],
    staffing: [],
    production: [],
    other: [],
  };
  for (const s of sentences) {
    buckets[classify(s)].push(s);
  }

  const production = parseProduction(buckets.production);
  const equipmentItems = parseEquipment(buckets.equipment);
  const safety = parseSafety(buckets.safety);
  const staffing = parseStaffing(buckets.staffing);
  const flags = buildFlags({ equipmentItems, safetyText: safety, staffingText: staffing });

  return {
    production,
    equipment: equipmentItems.map((i) => i.text),
    safety,
    staffing,
    flags,
  };
}
