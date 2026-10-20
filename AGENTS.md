# AGENTS.md — rules for all contributors and AI agents

This file is the single entry point for Claude Code, Codex, ChatGPT, Copilot, and humans. `CLAUDE.md` and `.github/copilot-instructions.md` point here.

## Must-follow

1. **Coding rules are mandatory**: read and follow [doc/en/coding-rules.md](doc/en/coding-rules.md) (canonical: [日本語](doc/jp/コーディングルール.md)).
2. **Always pull first**, every session and before every unit of work:
   `git fetch origin` then `git pull --rebase origin <current-branch>`. If this fails, do not start implementing. If the working tree has unrelated uncommitted changes you did not make, leave them untouched and do not stage them.
3. **Never commit directly to `main`.** Work on a branch (`feat/…`, `fix/…`, `docs/…`, `chore/…`), one feature per branch.
4. **At the end of every unit of work, open a PR** with the PR template filled in.
5. **Wait for CI**, then **self-review the full PR diff** against the coding rules. Fix problems and re-run CI.
6. **Merge only if** CI is green and the self-review finds no problems; otherwise fix or report. Squash-merge and delete the branch.

The detailed procedure is [doc/en/workflow.md](doc/en/workflow.md) (canonical: [日本語](doc/jp/ワークフロー/ワークフロー.md)).

## Project quick facts

- Python ≥ 3.10, standard library only; tests with `python -m pytest -q`.
- CLI: `python -m assam.cli --help`.
- Roadmap: [doc/en/roadmap.md](doc/en/roadmap.md). Pick work from there, one feature at a time.
- Japanese docs are canonical; keep the English pages in sync.
- Do not report unverified work as complete.
