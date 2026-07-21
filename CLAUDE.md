# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

**Static pages** — open any `.html` file directly in a browser, or serve the whole repo: `python3 -m http.server 8080` then visit `http://localhost:8080`. No build step.

**Blend Case Manager backend** (optional — the page works in offline/sample mode without it):
```
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 ftw_terminal_server.py       # http://<lan-ip>:8090
```
First run against pre-existing data: `python3 migrate_json_to_sqlite.py` (one-time `ftw_terminal_data.json` → `ftw_terminal.db` migration; safe no-op if there's nothing to migrate). See "Backend" below for details.

## Pages

| File | Purpose |
|---|---|
| `index.html` | Main dashboard — tank inventory, KPIs, action items, navigation tiles, Data Drop panel |
| `blend-case-manager.html` | Blend case lifecycle: originate → lock/sample → window → validate → book → receive → blend → settle → self-cert → close, with a closed-cases ledger |
| `receipt-schedule.html` | Inbound pipeline receipt schedule, with T4 export paste-in |
| `rack-demand-forecast.html` | Rack demand forecast by product and slot (static snapshot) |
| `spec-reference.html` | ASTM D4814-24a / DFW RFG / 40 CFR 1090 spec reference, incl. 2026 waiver overlay |
| `lab-procedures.html` | Step-by-step lab SOPs (dark sidebar nav layout) |
| `operator-proficiency.html` | ASTM repeatability/reproducibility self-certification testing |
| `coa-review.html` | Third-party Certificate of Analysis upload + review workflow |

All pages are self-contained single-file HTML with no external dependencies beyond the Montserrat Google Font (plus `pdf.js` on `coa-review.html` and the SheetJS `xlsx` CDN script on pages that parse spreadsheets).

## Shared client-side data files

Two plain-JS files (loaded via `<script src="...">`, not modules — they declare top-level `const`/functions in the shared global scope, so **never declare the same top-level identifier in more than one loaded script**) back "live data" features on top of the otherwise-static/mock content:

- **`fuels-snapshot.js`** — `TANK_ID_MAP`, `parseFuelsManagerFile()`, `saveSnapshot()`, `loadSnapshot()`. Parses a FuelsManager `.xlsx` export, picks the newest valid (`Available > 0 && Available <= WorkingCap * 1.2`) reading per tank, and persists to `localStorage` (`gp_fuelsManagerSnapshot`). Consumed by `index.html` only (tank farm fill levels + the Data Drop panel's drop-zone). Not currently wired into `blend-case-manager.html`.
- **`t4-schedule.js`** — `T4_KEY`, `GRADE_PRODUCT`, `parseT4Paste()` (returns `{batches, skipped}`), `normalizeDateTime()`, `saveT4()`, `loadT4()`. Parses tab-separated T4/Explorer export rows and persists to `localStorage` (`gp_t4Schedule`). Consumed by `index.html`'s Data Drop panel and `receipt-schedule.html`'s paste-in panel.

Both follow the same UI pattern wherever they're used: **idle** (drop-zone / paste box) → **preview** (parsed rows + Apply/Discard) → **confirmed** (persisted, with a "Live from ... · [time]" vs "Mock data" label). Applying never crashes on unmapped/invalid rows — they're silently skipped and counted.

## Backend — Blend Case Manager

`ftw_terminal_server.py` is a Flask + SQLite append-only store on port 8090 (CORS-enabled). `blend-case-manager.html` talks to it over plain HTTP if the operator enters a server URL in its connection bar (`SERVER.online`); otherwise the page runs in a fully-functional offline/sample mode with in-memory mock cases.

- **Storage**: `ftw_terminal.db`, single `records` table. Every create/update is an *insert*, never a mutation — the previous row is marked `current=0` (and its own stored JSON gets `_current: false`) and a new `current=1` row is appended. `case_id`/`iteration_id`/`receipt_id` are derived index columns (own `id` if that's the record's kind, else its `caseId`/`iterationId`/`receiptId` foreign key) so `/list` and `/case` can filter without scanning every JSON blob. The full record (all kind-specific fields) lives in the `data` TEXT column as JSON.
- **Routes**: `/health`, `/list?kind=`, `/case?id=`, `/create`, `/update`, `/checkout`, `/checkin`, `/force-release`, `/close` — all POST bodies/response shapes are stable; don't change them without updating `blend-case-manager.html` in the same change.
- **Concurrency**: every write route wraps its read-modify-insert in the module-level `threading.Lock()`. SQLite alone doesn't guarantee write ordering across concurrent requests — keep the lock.
- **Google Sheets export**: on `/close`, `append_closed_case_row()` best-effort appends a row to a "Closed Blend Cases" tab (`SHEET_ID` in the file) via a service account. Needs `google-credentials.json` (gitignored, not in repo) in the working directory; without it, `get_sheets_service()` logs a warning and every export call is a no-op — **this must never raise into the request**, since closing a case has to succeed regardless of Sheets availability.
- **Migration**: `migrate_json_to_sqlite.py` is one-time and refuses to run if `ftw_terminal.db` already exists (delete it first to re-migrate).

## Architecture

Every page shares the same design system — no shared CSS file exists; each page carries its own `<style>` block with identical custom properties.

### Color system

All colors are CSS custom properties defined in `:root` on every page:

| Variable | Use |
|---|---|
| `--slate` `#004F71` | Primary brand / headings |
| `--teal` `#00B398` | Accent / on-spec / CTA |
| `--lime` `#A9EE8A` | Gradient highlight |
| `--ulsd` `#C0882E` | ULSD grade color |
| `--ink` / `--ink-dim` / `--ink-faint` | Text hierarchy |
| `--line` `rgba(0,79,113,.13)` | Borders and dividers |
| `--gray` `#EEF3F6` | Input / card backgrounds |
| `--amber` / `--red` | Warning / alert states |

### Appbar pattern

Most pages use an identical sticky appbar structure:

```html
<header class="appbar">
  <div class="wm">GLOBAL<b>PARTNERS</b></div>
  <div class="divider"></div>
  <div class="appname">Page Name <span>· Subtitle</span></div>
  <div class="spacer"></div>
  <a href="index.html" class="back-link">← Dashboard</a>
</header>
```

`index.html` uses a search pill + Data Drop button + location pill in the right slot instead of a back-link. `lab-procedures.html` is the exception: it's a dark sidebar-nav layout with the appbar sitting above the sidebar (`.nav` is `position:sticky; top:64px` to sit below it) rather than the single-column pattern above.

### index.html layout

1. **`header.appbar`** — sticky top bar, with the Data Drop toggle button opening `#dataPanel` (T4 paste box + FuelsManager drop-zone, see "Shared client-side data files")
2. **`.hero`** — compliance status badge + margin opportunity feature (two-column grid)
3. **`.kpis`** — 4-column KPI row (on hand, receipts, rack demand, quality)
4. **`.midrow`** — tank farm visualization (`renderTankFarm()`, live-snapshot-aware) + action items panel
5. **`.grid` (Operations)** — navigation tiles: Terminal Inventory, Receipt Schedule, Blend Planner, Blend Case Manager, Rack Demand Forecast, Butane Supply
6. **`.grid` (Quality & Compliance)** — navigation tiles: Sampling/Testing, Calibration, Blend Documentation, Spec Compliance, Activity Log, Lab Procedures, Operator Proficiency, CoA Review, Spec Reference

Tiles with live pages use a real `href`; unbuilt tiles use `href="#"`.

### Tank farm (`.farm`)

Each `.tank[data-tank="TK55"]` (etc.) contains a `.ves` (vessel) with three absolutely positioned layers stacked bottom-up: `.heel` (hatched, non-pumpable), `.fill` (colored liquid), `.safe` (dashed amber line at safe-fill height). `renderTankFarm()` recomputes `.fill` height / `.pct` / `.bbl` from the FuelsManager snapshot when a tank has a valid reading (capacity inferred once from each tank's original mock bbl/pct ratio), falling back to the original hardcoded values otherwise — runs on load and again immediately after Apply in the Data Drop panel.

### Data

Baseline inventory numbers, quality readings, and the rack demand forecast are hardcoded/mock, marked `illustrative` or via the `MOCKSTAMP` badge in the bottom-right of each page. Where a live-data path exists (tank farm, blend generator tank volume, receipt schedule), it overlays on top of the mock data rather than replacing it in the source — see "Shared client-side data files."
