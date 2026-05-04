from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_upstream_destructive_lanes.py"
SPEC = spec_from_file_location("check_upstream_destructive_lanes", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_name_status_extracts_deletes_only() -> None:
    text = "\n".join(
        [
            "M\tscripts/check_llm_key.py",
            "D\tscripts/hive_ops_run.sh",
            "A\tdocs/releases/v0.10.4.md",
            "D\t.github/workflows/secret-scan.yml",
        ]
    )
    parsed = MODULE.parse_name_status(text)
    assert [r.path for r in parsed] == [
        "scripts/hive_ops_run.sh",
        ".github/workflows/secret-scan.yml",
    ]


def test_find_protected_deletes_flags_protected_paths() -> None:
    records = [
        MODULE.DeleteRecord(status="D", path="scripts/foo.sh"),
        MODULE.DeleteRecord(status="D", path="README.md"),
    ]
    flagged = MODULE.find_protected_deletes(
        records,
        protected_prefixes=MODULE.PROTECTED_PREFIXES,
        allow_delete_prefixes=(),
    )
    assert [r.path for r in flagged] == ["scripts/foo.sh"]


def test_find_protected_deletes_honors_allow_prefixes() -> None:
    records = [
        MODULE.DeleteRecord(status="D", path="scripts/tmp/old.sh"),
        MODULE.DeleteRecord(status="D", path="scripts/runbook.sh"),
    ]
    flagged = MODULE.find_protected_deletes(
        records,
        protected_prefixes=MODULE.PROTECTED_PREFIXES,
        allow_delete_prefixes=("scripts/tmp/",),
    )
    assert [r.path for r in flagged] == ["scripts/runbook.sh"]


def test_main_fails_when_protected_deletes_present(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        MODULE,
        "_run_git_diff",
        lambda _base, _up: "D\tscripts/acceptance_gate_presets.sh\nM\tscripts/check_llm_key.py\n",
    )
    rc = MODULE.main(["--base-ref", "HEAD", "--upstream-ref", "upstream/main"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "protected destructive deletes detected" in out
    assert "scripts/acceptance_gate_presets.sh" in out


def test_main_passes_when_only_non_protected_deletes(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        MODULE,
        "_run_git_diff",
        lambda _base, _up: "D\tdocs/releases/old.md\nM\tscripts/check_llm_key.py\n",
    )
    rc = MODULE.main(["--base-ref", "HEAD", "--upstream-ref", "upstream/main"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no protected destructive deletes" in out
