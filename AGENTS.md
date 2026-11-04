# AGENTS.md — shared entry point

Applies to Claude Code, Codex, ChatGPT, Copilot, and human contributors. `CLAUDE.md` and `.github/copilot-instructions.md` point here; keep the detailed rules in their linked sources, not in copies of this file.

## Required for each work unit

1. Check `git status`, then run `git fetch origin` and `git pull --rebase origin <current-branch>` before editing. If synchronization fails, stop. Preserve unrelated uncommitted work.
2. Follow the [coding rules](doc/jp/コーディングルール.md) ([English](doc/en/coding-rules.md)). Use one `feat/`, `fix/`, `docs/`, or `chore/` branch per feature; never commit to `main`.
3. Follow the [one-unit workflow](doc/jp/ワークフロー/ワークフロー.md) ([English](doc/en/workflow.md)): fill the PR template, wait for CI, self-review the full PR diff, then squash-merge and delete the branch only when both are clean. Report unverified work honestly.

## Design first (avoid rework)

Implementation follows the design documents ([日本語・正本](doc/jp/設計/README.md) / [English](doc/en/design/README.md)).

1. Pick a work package (WP) in the [implementation plan](doc/jp/設計/実装計画.md) ([English](doc/en/design/implementation-plan.md)); do not start unless its prerequisites are on `main` and no unresolved blocker (`Q*`) applies.
2. Read only that WP's row and the linked design section, plus the [decision log](doc/jp/設計/決定ログ.md) ([English](doc/en/design/decision-log.md)) if a choice is unclear.
3. If the design is missing or contradicts the code or an Issue, stop and fix the design in a separate `docs/` PR first. Do not decide silently in code.

## Fix broken tooling; do not burn usage

- A broken hook, script, CI step, path, plugin, or review tool is fixed on the spot, not reported and left waiting for a decision. Investigate the cause and repair it (or report once with cause and fix only if it is outside your authority: another repository, billing, secrets). This applies to the whole environment, not just one hook.
- Automated notifications that are empty or identical to an earlier one get at most one short line, never a repeated boilerplate reply. On the second occurrence, switch to diagnosing and fixing the cause.
- Save usage without lowering quality or scope: read and print only what the task needs, batch independent checks, and do not re-run or re-read what is already established.

## Read only what this task needs

- Set the goal and acceptance check. Search paths or symbols first (`rg --files`, `rg -n`), then read the relevant source, tests, and canonical specification sections. Stop widening the search once the scope and verification are clear.
- For an unfamiliar area, select only the matching row in the [task-to-source map](doc/jp/作業別コンテキスト案内.md) ([English](doc/en/task-context-map.md)); it is a starting point, not a substitute for current code.
- For Core target coverage or mapping work, open the focused [target-mappings skill](.agents/skills/assam-target-mappings/SKILL.md) only for that task. Its path is explicit so agents need not rely on product-specific skill discovery.
- Normally skip unrelated docs, old logs, caches, and generated files; read them when the task or verification actually depends on them. Do not treat a search hit or a structural checker as proof of runtime semantics.

Python ≥ 3.10, standard library only; tests: `python -m pytest -q`. Japanese docs are canonical; update corresponding English pages in the same change. Choose the next bounded unit from the [roadmap](doc/jp/開発予定.md) or a current Issue.
