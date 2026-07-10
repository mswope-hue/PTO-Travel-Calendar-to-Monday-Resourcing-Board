# Project: PTO Travel Calendar → Monday Resourcing Board

## Automation Registry Rule

Whenever a new automation, integration, or scheduled script is built in this project (or any project in this workspace), **register it on the Monday Automation Registry board** (board ID: `18408548437`, https://gettys-group.monday.com/boards/18408548437).

Create one item per script using these columns:

| Column ID | What to fill in |
|---|---|
| `name` | Short descriptive name (e.g. "PTO Calendar → Resourcing Board") |
| `long_text_mm2dvf7s` | Plain-English description of what it does |
| `text_mm2dza7z` | Schedule / trigger frequency |
| `text_mm2d9920` | Which Monday boards it reads/writes |
| `multiple_person_mm2dbm1b` | Owner — Matt Swope ID: `89457676` |
| `long_text_mm2d92h9` | Repo link, prerequisites, how to run, known quirks |
| `text_mm2dq8ny` | Script file names |
| `text_mm2dsjb9` | Command to run it |
| `color_mm2dadef` | Status: `In Development` → `Active` once live |
| `color_mm2d938c` | Last Run Status: start as `Never Run` |
| `color_mm2dqpqc` | Trigger Type: `Scheduled`, `Webhook`, `Manual CLI`, or `Manual Batch` |

## This Project

**What it does:** Checks the Outlook Travel calendar for new events containing "PTO" or "Flex Friday" in the title. Extracts the employee name, calculates business hours (1 day = 8 hrs, weekdays only; half days = 4 hrs), and creates/updates a subitem on the 👥Resourcing Board under the matching month row — **PTO goes under "02 - PTO", Flex Friday goes under "06 - Flex Friday"**.

**PRIMARY IMPLEMENTATION — Power Automate + Claude daily routine (not the code in this repo):**
Microsoft 365 connectors cannot be attached to Claude routines (tested July 2026), so Outlook access lives in **Power Automate** instead: a flow on Matt's Office 365 account watches the Travel calendar and forwards matching events to the **PTO Intake board** (ID `18421462569`) via the board's add-items-by-email address. Item names arrive as `{event title} | {start} | {end} | allday:{true/false}`.

The daily Claude routine then only needs the **monday.com connector**. If you are the daily routine:
1. On the PTO Intake board (`18421462569`), get all items whose **Processed** status (column `color_mm546hgy`) is "New" or empty.
2. Parse each item name: `{event title} | {start} | {end} | allday:{true/false}`. If the title does not contain "PTO" or "Flex Friday" (case-insensitive), set Processed = Done and skip it.
3. Person = title minus the keyword and any half-day marker. Hours = weekdays × 8; **if the title notes a half day ("half day", "1/2 day", "½ day"), use 4 hours per day.** For all-day events the end date is exclusive (Outlook convention) — subtract one day.
4. Month row = item named `{Month} YYYY` on board `18397329110` whose Project Name column is **"02 - PTO" for PTO events** or **"06 - Flex Friday" for Flex Friday events**. Split hours across months if the range spans months.
5. **Upsert, don't duplicate:** if a subitem for that person already exists under the month row, update its hours/date/notes instead of creating a new one.
6. Set the intake item's Processed status to **Done** (or **Error** with an update explaining why).
7. Finish with a short notification summarizing what changed (or that nothing was found).

**Board:** 👥Resourcing Board — ID `18397329110`
- "02 - PTO" parent items are named `{Month} YYYY` (e.g. "June 2026")
- PTO subitems board ID: `18397329129`
- Subitem columns: `numeric_mkzkw9qz` (planned hrs), `date_mm33e7b7` (start date), `text_mm35wh5a` (notes)

**BACKUP IMPLEMENTATION — this repo's Python code (currently disabled):**
GitHub Actions workflow (`.github/workflows/poll-pto.yml`, daily ~6:23am Central) running `python main.py poll` via Microsoft Graph. Blocked on Azure app registration (IT won't grant it). Required secrets if ever revived: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `OUTLOOK_USER_EMAIL`, `MONDAY_API_KEY`, `MONDAY_BOARD_ID`.

**Registry entry:** https://gettys-group.monday.com/boards/18408548437/pulses/12255877627
