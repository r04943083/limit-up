# CLAUDE.md — working rules for this repo

## Commit authorship (IMPORTANT)
- Commits must be authored **solely by the repository owner** (`r04943083 <willu.star@gmail.com>`).
- **Do NOT add any AI attribution** to commits or PRs — no `Co-Authored-By: Claude …`,
  no "Generated with Claude Code", no AI mention in the commit message, trailer, or body.
- Keep commit messages plain and descriptive of the change only.

## Running the app
- Start (prod build + serve API:8000 + web:3000): `scripts/start-web.sh`
- Dev (hot-reload, no build): `scripts/start-web.sh --dev`
- Stop: `scripts/stop-web.sh`
- `uv` is at `~/.local/bin` — ensure it's on `PATH`.

## Conventions
- Colors: **red = up, green = down** (Futu / A-share convention).
- All numbers come from `packages/lucore/compute` + `data`; the LLM only narrates/scores.
- Never commit `data/` (the user's DB/portfolio) or `reference/` (personal screenshots/exports).
- Communicate with the owner in Chinese.
