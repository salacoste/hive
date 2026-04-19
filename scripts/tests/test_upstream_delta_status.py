from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "upstream_delta_status.py"
SPEC = spec_from_file_location("upstream_delta_status", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parse_name_status_handles_basic_and_rename_lines() -> None:
    raw = "\n".join(
        [
            "M\tREADME.md",
            "A\tcore/tests/test_event_bus.py",
            "R100\told/path.md\tnew/path.md",
        ]
    )
    entries = MODULE.parse_name_status(raw)
    assert len(entries) == 3
    assert entries[0].status == "M"
    assert entries[0].path == "README.md"
    assert entries[2].status == "R100"
    assert entries[2].path == "new/path.md"


def test_classify_paths_groups_into_expected_buckets() -> None:
    buckets = MODULE.classify_paths(
        [
            "README.md",
            "core/framework/agents/queen/queen_memory.py",
            "core/framework/agents/queen/recall_selector.py",
            "untracked/path.py",
        ]
    )
    assert buckets["bucket_a_low_risk"] == ["README.md"]
    assert buckets["bucket_b_medium_risk"] == ["core/framework/agents/queen/recall_selector.py"]
    assert buckets["bucket_c_high_risk"] == ["core/framework/agents/queen/queen_memory.py"]
    assert buckets["other_unclassified"] == ["untracked/path.py"]


def test_build_report_counts_entries() -> None:
    raw = "M\tREADME.md\nA\tcore/tests/test_event_bus.py\n"
    report = MODULE.build_report("HEAD", "origin/main", raw)
    assert report["base_ref"] == "HEAD"
    assert report["target_ref"] == "origin/main"
    assert report["total_entries"] == 2
    assert report["buckets"]["bucket_a_low_risk"]["count"] == 1
    assert report["buckets"]["bucket_b_medium_risk"]["count"] == 1
