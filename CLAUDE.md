# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

Open any `.html` file directly in a browser — no build step, no server required. For a local server: `python3 -m http.server 8080` then visit `http://localhost:8080`.

## Pages

| File | Purpose |
|---|---|
| `index.html` | Main dashboard — tank inventory, KPIs, action items, navigation tiles |
| `blend-generator.html` | Butane blend calculator (linked from dashboard) |
| `receipt-schedule.html` | Inbound pipeline receipt schedule (linked from dashboard) |
| `rack-demand-forecast.html` | Rack demand forecast by product and slot (linked from dashboard) |

All pages are self-contained single-file HTML with no external dependencies beyond the Montserrat Google Font.

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

Every page uses an identical sticky appbar structure:

```html
<header class="appbar">
  <div class="wm">GLOBAL<b>PARTNERS</b></div>
  <div class="divider"></div>
  <div class="appname">Page Name <span>· Subtitle</span></div>
  <div class="spacer"></div>
  <a href="index.html" class="back-link">← Dashboard</a>
</header>
```

The dashboard (`index.html`) uses a search pill and location pill in the right slot instead of a back-link.

### index.html layout

1. **`header.appbar`** — sticky top bar
2. **`.hero`** — compliance status badge + margin opportunity feature (two-column grid)
3. **`.kpis`** — 4-column KPI row (on hand, receipts, rack demand, quality)
4. **`.midrow`** — tank farm visualization + action items panel
5. **`.grid` (Operations)** — navigation tiles: Terminal Inventory, Receipt Schedule, Blend Planner, Blend Generator, Rack Demand Forecast, Butane Supply
6. **`.grid` (Quality & Compliance)** — navigation tiles: Sampling/Testing, Calibration, Blend Documentation, Spec Compliance, Activity Log

Tiles with live pages use a real `href`; unbuilt tiles use `href="#"`.

### Tank farm (`.farm`)

Each `.tank` contains a `.ves` (vessel) with three absolutely positioned layers stacked bottom-up: `.heel` (hatched, non-pumpable), `.fill` (colored liquid), `.safe` (dashed amber line at safe-fill height). Heights are inline `style` percentages.

### blend-generator.html — Butane Blend Calculator

**Inputs:** Tank Number, Tank Volume (bbl), Target RVP (psi), and three sample rows (Upper / Middle / Lower) each with PTOT and RVP.

**Validation:** PTOT is QC-only. If any RVP > PTOT, both inputs highlight red with an inline error. PTOT does not enter the volume calculation.

**Calculation:**
1. Adjust each PTOT reading: `RVP_adj = ROUND((0.965 × PTOT) − 0.548, 2)`
2. Average the three adjusted values → `baseRVP`
3. `V_butane = tankVolume × 0.02 × (targetRVP − baseRVP)`
4. `trucks = Math.floor(V_butane / 190)` — no partial trucks
5. Remainder shown as "X bbl to next truck" when not an exact multiple

**Results card:** teal/lime gradient (matching `.marginfeat` on dashboard), shows Avg Base RVP / Butane Required / Trucks with a per-row adjusted RVP breakdown. Copy Results button writes plain-text summary to clipboard.

### Data

All inventory numbers and quality readings in `index.html` are hardcoded. Quality readings are marked `illustrative` pending a lab feed. The `MOCKSTAMP` fixed badge in the bottom-right documents this on every page.
