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
- Do not report unverified items as complete.

## 3. Record and finish

- Update the README, specifications, and roadmap as appropriate.
- Record the work, verification results, unresolved issues, and next task.
- Review the diff and commit the feature as a focused unit.
- If sharing the work, push it and verify the branch and commit.

A unit is complete only after remote synchronization, implementation, tests, required documentation updates, Git recording, and unresolved-work notes are all handled.
