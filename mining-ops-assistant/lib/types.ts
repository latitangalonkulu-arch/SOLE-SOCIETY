export type Role = "supervisor" | "manager";
export type Shift = "Day" | "Night";

export interface User {
  id: string;
  name: string;
  email: string;
  passwordHash: string;
  role: Role;
  section?: string;
}

export interface ShiftReport {
  id: string;
  supervisorId: string;
  supervisorName: string;
  shift: Shift;
  section: string;
  rawUpdate: string;
  production: string;
  equipment: string[];
  safety: string;
  staffing: string;
  flags: string[];
  createdAt: string;
}

export interface Db {
  users: User[];
  reports: ShiftReport[];
}

export interface ParsedReport {
  production: string;
  equipment: string[];
  safety: string;
  staffing: string;
  flags: string[];
}

export interface SessionPayload {
  uid: string;
  name: string;
  role: Role;
  section?: string;
}
