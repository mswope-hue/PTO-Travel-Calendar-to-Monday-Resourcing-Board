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

**What it does:** Polls the Outlook Travel calendar via Microsoft Graph API for new events containing "PTO" or "Flex Friday". Extracts the employee name, calculates business hours (1 day = 8 hrs), and creates/updates a subitem on the 👥Resourcing Board under the matching "02 - PTO" month row.

**Board:** 👥Resourcing Board — ID `18397329110`
- "02 - PTO" parent items are named `{Month} YYYY` (e.g. "June 2026")
- PTO subitems board ID: `18397329129`
- Subitem columns: `numeric_mkzkw9qz` (planned hrs), `date_mm33e7b7` (start date), `text_mm35wh5a` (notes)

**Schedule:** Daily at ~6:23am Central via GitHub Actions (`.github/workflows/poll-pto.yml`)

**Required secrets (GitHub repo secrets):**
- `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- `OUTLOOK_USER_EMAIL`
- `MONDAY_API_KEY`, `MONDAY_BOARD_ID`

**Registry entry:** https://gettys-group.monday.com/boards/18408548437/pulses/12255877627
