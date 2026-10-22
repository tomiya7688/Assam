---
name: assam-target-mappings
description: Validate Assam Core target coverage manifests and declarative mapping tables when changing target files, their schemas, or checker behavior.
---

# Assam target mappings

Use only for Core target coverage/mapping work. Follow the repository [workflow](../../../doc/jp/ワークフロー/ワークフロー.md) for Git, PR, CI, and review; this skill covers the target-specific checks.

1. Search for the affected architecture/profile pair, then read only its manifest, mapping table, relevant [registry](../../../assam/data/instruction_registry.json) entries, schema, and tests. The [Core profile](../../../doc/jp/assam-core.md) is the canonical design context. Check `assam/target_coverage.py` only when changing checker behavior.
2. For each changed coverage manifest, run `python -m assam.cli check-target-coverage <manifest.json>`. If using `scaffold-target-coverage`, review every `out_of_scope` classification before accepting it.
3. For each changed mapping, run `python -m assam.cli check-target-mappings <mapping.json> --coverage <matching-manifest.json>`; resolve missing `in_scope` sequences and contradictory `out_of_scope` declarations.
4. For the required x64, ARM64, and RISC-V set, run `python -m assam.cli check-target-matrix <x64-manifest> <arm64-manifest> <riscv-manifest> --mapping <x64-table> --mapping <arm64-table> --mapping <riscv-table>`. Match additional custom-target/profile tables when supplied.

These checks prove registry references, structure, and declared coverage only. They do **not** prove executable translation or semantic equivalence; report those separately. Run the focused target tests and the repository test suite before PR.
