from pathlib import Path

from assam.target_coverage import check_target_mappings

TARGETS = Path(__file__).resolve().parents[1] / "examples" / "targets"


def test_riscv64_mapping_matches_its_coverage_manifest():
    report = check_target_mappings(
        TARGETS / "riscv64-rv64i-draft.mapping.json",
        coverage_path=TARGETS / "riscv64-rv64i-draft.coverage.json",
    )
    assert report["coverage"]["in_scope"] == 16
    assert report["coverage"]["out_of_scope"] == 5
