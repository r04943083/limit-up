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

## Definition of Done (IMPORTANT)
Every feature is only "done" after **all** of these, in order:
1. **Unit tests** — backend logic (`packages/lucore/tests`) covering the new behavior.
2. **E2E tests** — Playwright spec(s) in `apps/web/e2e` for the new UI/flow.
3. **Full code review** — review the whole change for correctness, regressions, conventions.
4. **Push workflow** — only then commit (author = owner, no AI attribution) and push.
Do not consider work complete or report it as done until 1–4 are satisfied.

## Conventions
- Colors: **red = up, green = down** (Futu / A-share convention).
  Note: the **English** Futubull site (futunn.com/en) uses Western colors (red = down) —
  when studying Futu's UI for reference, use the **Chinese** site to match this convention.
- All numbers come from `packages/lucore/compute` + `data`; the LLM only narrates/scores.
- Never commit `data/` (the user's DB/portfolio) or `reference/` (personal screenshots/exports).
- Communicate with the owner in Chinese.
