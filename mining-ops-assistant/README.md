# Dlamini Ridge Mining — AI Operations Assistant (pilot demo)

A working build of the pilot proposed in *AI Operations Assistant for Mining
Companies*: a supervisor types (or pastes a voice-note transcript of) a quick
end-of-shift update, the system turns it into a clean, standard shift report
— production, equipment, safety, staffing, and a flag for the manager — the
supervisor reviews and edits it, and it's filed straight to the manager's
dashboard.

This is a self-contained version: no API keys, no external accounts, nothing
to sign up for. It uses a rule-based text parser instead of a live AI model
call, and stores data in a local file instead of a cloud database, so it runs
immediately on a laptop with no setup. See **Upgrade path** below for how to
swap in a real LLM and a real database later without changing the rest of
the app.

## Running it

```bash
npm install
npm run dev
```

Then open http://localhost:3000 — you'll land on the login page.

### Demo accounts (password: `pilot2024` for all)

| Role                    | Email                          |
| ------------------------ | ------------------------------ |
| Manager                  | manager@dlaminiridge.co.za     |
| Supervisor — Section 4   | thabo@dlaminiridge.co.za       |
| Supervisor — Section 7   | nomvula@dlaminiridge.co.za     |

Demo data (a handful of historical shift reports, including two earlier
Truck 12 breakdowns) is generated automatically the first time the app runs,
so the manager dashboard isn't empty on first login.

### Suggested demo script (matches the proposal's example)

1. Log in as **Thabo** (a supervisor).
2. Click **"Use example update"**, then **"Generate report"**. This fills in
   the free-text box with: *"Day shift, Section 4. Truck 12 broke down at 10,
   hydraulic leak, back by 2. About 800 tons moved. One near miss. Short two
   people."*
3. Show the structured draft it produces (production / equipment / safety /
   staffing / flag for manager) — all editable.
4. Click **"Submit to manager"**.
5. Log out, log in as **Sipho** (the manager).
6. Point out the dashboard: the new report at the top, the flag, and the
   **recurring equipment issue callout** — Truck 12 has now broken down 3
   times in the last 14 days (two from seed data, one just filed), which is
   exactly the "catches repeat problems early" benefit from the proposal.
7. Try the search box (e.g. "near miss" or "Thabo") and the "Flagged only"
   checkbox.

## How this maps to the proposal

| Proposal section                         | In this app                                                         |
| ----------------------------------------- | -------------------------------------------------------------------- |
| 3. How it works                           | Supervisor page: raw update → generated draft → edit → submit        |
| 4. Example output                         | The rule-based parser (`lib/parser.ts`) produces this exact shape    |
| 5. Benefits — "catches repeat problems"   | `lib/insights.ts` flags equipment with 2+ breakdowns in 14 days      |
| 5. Benefits — "searchable safety record"  | Manager dashboard search box, matches across all report fields       |
| 8. Data and safety — "supervisor reviews" | Draft is always editable before filing; nothing is sent unreviewed   |

## Architecture

- **Next.js App Router** (v16), TypeScript, Tailwind v4.
- **Auth**: email/password accounts, bcrypt-hashed, signed HTTP-only session
  cookie (HMAC-SHA256, no external auth provider). See `lib/auth.ts`.
- **Parser**: `lib/parser.ts` is a keyword/regex-based reader, not a model
  call — it classifies sentences into production/equipment/safety/staffing
  buckets and drafts a flag when it sees a breakdown, incident, or
  short-staffed shift. It's intentionally a *first draft generator*: the
  supervisor always reviews and can edit every field before it's filed,
  which is also what the proposal's design calls for ("a human always has
  the final say").
- **Storage**: a single JSON file at `data/db.json`, created with seed data
  on first run. Fine for a pilot (a handful of supervisors, a few reports a
  day); see below for what to swap in beyond that.
- **Server Actions** (not a separate REST API) handle preview-parsing,
  filing a report, login, and logout.

## Upgrade path (for a real multi-mine pilot)

Two things in this build were deliberately kept simple so it needs zero
external accounts. Both are isolated behind small modules, so neither
requires touching the UI:

1. **Replace the parser with a live Claude API call.** Swap the body of
   `parseShiftUpdate` in `lib/parser.ts` for a prompt to Claude that returns
   the same `{ production, equipment, safety, staffing, flags }` shape.
   This gets you real language understanding (voice-note transcripts,
   messier phrasing, local terminology) instead of keyword matching.
2. **Replace the JSON file with Supabase (Postgres).** Swap the functions in
   `lib/db.ts` (`getUserByEmail`, `addReport`, `listAllReports`, etc.) for
   Supabase queries. This gets you a real multi-instance database, row-level
   security per mine, and a place to plug in Supabase Auth if you want
   magic-link or SSO login instead of passwords.

Neither change touches `app/supervisor`, `app/manager`, or the auth/session
logic — they only call the functions these two modules already export.

## Limitations (by design, for a pilot demo)

- The parser is rule-based: it handles the phrasing style in the proposal's
  example well, but won't match a real LLM's flexibility with unusual
  phrasing. The supervisor edit step exists specifically to cover this gap.
- Single-process, single-file storage — fine for a pilot on one section of
  one mine, not for production multi-mine scale (see Upgrade path).
- No SMS/WhatsApp/voice-note ingestion yet — update is typed directly into
  the web form. Voice notes would need a transcription step (e.g. Whisper or
  Claude's audio input) ahead of the same parser.
