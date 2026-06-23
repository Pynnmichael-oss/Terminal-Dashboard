# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running

Open `index.html` directly in a browser — no build step, no server required. For a local server: `python3 -m http.server 8080` then visit `http://localhost:8080`.

## Architecture

The entire dashboard is a single self-contained file: `index.html`. All CSS lives in a `<style>` block in the `<head>`; all content is hardcoded HTML. There is no JavaScript, no external data feed, and no build toolchain.

### Color system

All colors are CSS custom properties defined in `:root`:

| Variable | Use |
|---|---|
| `--slate` `#004F71` | Primary brand / headings |
| `--teal` `#00B398` | Accent / on-spec / CTA |
| `--lime` `#A9EE8A` | Gradient highlight |
| `--ulsd` `#C0882E` | ULSD grade color |
| `--ink` / `--ink-dim` / `--ink-faint` | Text hierarchy |
| `--amber` / `--red` | Warning / alert states |

### Layout structure

1. **`header.appbar`** — sticky top bar (logo, nav, search pill, location pill)
2. **`.hero`** — two-column: compliance status badge + margin opportunity feature
3. **`.kpis`** — 4-column KPI row (on hand, receipts, rack demand, quality)
4. **`.midrow`** — tank farm visualization + action items panel
5. **`.grid` sections** — Operations tiles, then Quality & Compliance tiles

### Tank farm (`.farm`)

Each `.tank` contains a `.ves` (vessel) with three absolutely positioned layers stacked bottom-up: `.heel` (hatched, non-pumpable), `.fill` (colored liquid), `.safe` (dashed line at safe-fill height). Heights are set as inline `style` percentages representing actual tank state.

### Data

All inventory numbers (volumes, RVP readings, flash points) are hardcoded. Quality readings are explicitly marked `illustrative` pending a lab data feed. The `MOCKSTAMP` fixed badge in the bottom-right documents this status visually.
