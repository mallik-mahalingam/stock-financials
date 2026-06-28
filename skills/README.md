# Agent skills (Cursor / Claude)

Each subfolder contains **only** a `SKILL.md` — agent instructions, not executable code.

| Skill | Folder | Scripts (repo root) |
|-------|--------|---------------------|
| **stock-financials** | `stock-financials/` | `~/src/stock-financials/scripts/sec_financials.py`, … |
| **stock-summary** | `stock-summary/` | `~/src/stock-financials/scripts/build_summary.py`, `fetch_summary.py`, `render_summary_canvas.py` |

## Cursor setup

From repo root, run `./setup.sh` (links both skills), or manually:

```bash
ln -sf ~/src/stock-financials/skills/stock-financials ~/.cursor/skills/stock-financials
ln -sf ~/src/stock-financials/skills/stock-summary ~/.cursor/skills/stock-summary
```
