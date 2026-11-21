import "server-only";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import bcrypt from "bcryptjs";
import type { Db, ShiftReport, User } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_FILE = path.join(DATA_DIR, "db.json");

const DEMO_PASSWORD = "pilot2024";

function daysAgoIso(days: number, hour: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

function buildSeed(): Db {
  const hash = (pw: string) => bcrypt.hashSync(pw, 10);

  const manager: User = {
    id: "u-manager-1",
    name: "Sipho Dlamini",
    email: "manager@dlaminiridge.co.za",
    passwordHash: hash(DEMO_PASSWORD),
    role: "manager",
  };
  const thabo: User = {
    id: "u-sup-1",
    name: "Thabo Nkosi",
    email: "thabo@dlaminiridge.co.za",
    passwordHash: hash(DEMO_PASSWORD),
    role: "supervisor",
    section: "Section 4",
  };
  const nomvula: User = {
    id: "u-sup-2",
    name: "Nomvula Khumalo",
    email: "nomvula@dlaminiridge.co.za",
    passwordHash: hash(DEMO_PASSWORD),
    role: "supervisor",
    section: "Section 7",
  };

  const reports: ShiftReport[] = [
    {
      id: "r-1",
      supervisorId: thabo.id,
      supervisorName: thabo.name,
      shift: "Day",
      section: "Section 4",
      rawUpdate:
        "Day shift, Section 4. Truck 12 broke down at 9, hydraulic leak, back by 11. About 650 tons moved. No safety incidents. Full crew.",
      production: "Approximately 650 tons moved.",
      equipment: ["Truck 12 down 09:00 to 11:00, hydraulic leak, repaired."],
      safety: "No safety incidents reported.",
      staffing: "Full crew.",
      flags: ["Truck 12 hydraulic issue — check maintenance history."],
      createdAt: daysAgoIso(5, 18),
    },
    {
      id: "r-2",
      supervisorId: nomvula.id,
      supervisorName: nomvula.name,
      shift: "Night",
      section: "Section 7",
      rawUpdate:
        "Night shift, Section 7. Loader 5 operational. About 720 tons moved. No safety incidents. Full crew.",
      production: "Approximately 720 tons moved.",
      equipment: ["Loader 5 operational."],
      safety: "No safety incidents reported.",
      staffing: "Full crew.",
      flags: [],
      createdAt: daysAgoIso(4, 6),
    },
    {
      id: "r-3",
      supervisorId: thabo.id,
      supervisorName: thabo.name,
      shift: "Day",
      section: "Section 4",
      rawUpdate:
        "Day shift, Section 4. Truck 12 down again at 13, electrical fault, back by 4. 600 tons moved. No safety incidents. Short one person.",
      production: "Approximately 600 tons moved.",
      equipment: ["Truck 12 down 13:00 to 16:00, electrical fault, repaired."],
      safety: "No safety incidents reported.",
      staffing: "One person short.",
      flags: ["Truck 12 electrical issue — check maintenance history."],
      createdAt: daysAgoIso(2, 18),
    },
    {
      id: "r-4",
      supervisorId: nomvula.id,
      supervisorName: nomvula.name,
      shift: "Night",
      section: "Section 7",
      rawUpdate:
        "Night shift, Section 7. One near miss, worker walked behind a reversing truck, verbal correction given. 540 tons moved. Full crew.",
      production: "Approximately 540 tons moved.",
      equipment: [],
      safety: "One near miss reported. Follow-up recommended.",
      staffing: "Full crew.",
      flags: ["Safety follow-up required."],
      createdAt: daysAgoIso(1, 6),
    },
  ];

  return { users: [manager, thabo, nomvula], reports };
}

function ensureDb(): Db {
  if (!fs.existsSync(DB_FILE)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    const seeded = buildSeed();
    fs.writeFileSync(DB_FILE, JSON.stringify(seeded, null, 2));
    return seeded;
  }
  const raw = fs.readFileSync(DB_FILE, "utf-8");
  return JSON.parse(raw) as Db;
}

function writeDb(db: Db): void {
  fs.writeFileSync(DB_FILE, JSON.stringify(db, null, 2));
}

export function getUserByEmail(email: string): User | undefined {
  const db = ensureDb();
  return db.users.find((u) => u.email.toLowerCase() === email.toLowerCase());
}

export function getUserById(id: string): User | undefined {
  const db = ensureDb();
  return db.users.find((u) => u.id === id);
}

export function listAllReports(): ShiftReport[] {
  const db = ensureDb();
  return [...db.reports].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function listReportsBySupervisor(supervisorId: string): ShiftReport[] {
  return listAllReports().filter((r) => r.supervisorId === supervisorId);
}

export function addReport(input: Omit<ShiftReport, "id" | "createdAt">): ShiftReport {
  const db = ensureDb();
  const report: ShiftReport = {
    ...input,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  };
  db.reports.push(report);
  writeDb(db);
  return report;
}

export const demoCredentials = {
  password: DEMO_PASSWORD,
};
