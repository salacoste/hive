from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "render_unclassified_decision_report.py"
SPEC = spec_from_file_location("render_unclassified_decision_report", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_render_report_includes_summary_and_table() -> None:
    report = MODULE.render_report(
        ["a.py", "b.py"],
        {
            "a.py": {"decision": "already-absorbed", "backlog_items": [1]},
            "b.py": {"decision": "defer", "backlog_items": [2, 3]},
        },
    )
    assert "Total unclassified paths: 2" in report
    assert "- already-absorbed: 1" in report
    assert "- defer: 1" in report
    assert "| `a.py` | `already-absorbed` | `1` |" in report
    assert "| `b.py` | `defer` | `2, 3` |" in report


def test_render_report_marks_missing_decisions() -> None:
    report = MODULE.render_report(["x.py"], {})
    assert "- missing: 1" in report
    assert "| `x.py` | `missing` | `` |" in report
