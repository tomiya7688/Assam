# ASSAM Development Workflow

Language: [日本語](../jp/ワークフロー/ワークフロー.md) | English

This document defines the steps for one unit of work.

## 1. Start

- Review `doc/en/roadmap.md` and the related specification; limit the task to one feature.
- Check `git status` and preserve unrelated existing changes.
- Incorporate remote changes before starting work.

```text
git fetch origin
git pull --rebase origin <current-branch>
```

If conflicts occur, resolve them before rerunning validation. If remote synchronization fails, do not start implementation.

## 2. Implement and verify

- Review the existing API and tests before implementation.
- Add tests for the feature being changed.
- Run relevant tests and, as needed, validate the CLI, VM, JSON, and terminal communication.
- When adding or changing target coverage manifests, run `assam check-target-coverage <manifest.json>` on each file and `assam check-target-matrix <x64.json> <arm64.json> <riscv.json>` for the required targets. If starting from `assam scaffold-target-coverage <architecture> <profile>`, review and reclassify every `out_of_scope` entry. These commands check declarations only; they do not validate implemented or executable instruction translations.
- When adding or changing target mapping tables, run `assam check-target-mappings <mapping.json> --coverage <manifest.json>` against the coverage declarations for the same target/profile. Resolve missing `in_scope` sequences and conflicts with `out_of_scope` declarations, and verify semantic and execution equivalence separately.
- Once mapping tables exist for the required targets, add `--mapping <mapping.json>` for each table to `assam check-target-matrix <x64.json> <arm64.json> <riscv.json>` to check the batch. Supply matching tables for any additional custom-target or profile manifests too.
- Do not report unverified items as complete.

## 3. Record and finish

- Update the README, specifications, and roadmap as appropriate.
- Record the work, verification results, unresolved issues, and next task.
- Review the diff and commit the feature as a focused unit.

## 4. Pull request, CI, self-review, merge

Claude Code, Codex, ChatGPT, Copilot, and humans all follow the same procedure. Never commit directly to `main`; work on a `feat/`, `fix/`, `docs/`, or `chore/` branch.

1. Re-run `git fetch origin` and `git pull --rebase origin main`; resolve conflicts and re-run the tests.
2. Push the branch and open a PR with `.github/pull_request_template.md` filled in (`gh pr create`).
3. Wait for CI (`.github/workflows/ci.yml`) to finish. Check it with `gh pr checks`; do not poll in a tight loop.
4. Self-review the whole PR diff (`gh pr diff`) against [coding-rules.md](coding-rules.md): scope (one feature), tests, documentation in both languages, no unrelated or other contributors' changes, no unverified claims. Record the result in the PR's Self-review section.
5. If CI fails or the review finds problems, fix them on the branch, push, and repeat from step 3.
6. Merge only when CI is green and the self-review found no problems: `gh pr merge --squash --delete-branch`. Otherwise leave the PR open and report why.
7. After merging, `git switch main` and `git pull --rebase origin main`.

A unit is complete only after remote synchronization, implementation, tests, required documentation updates, the merged PR with passing CI, and unresolved-work notes are all handled.
