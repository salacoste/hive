from importlib.util import module_from_spec, spec_from_file_location
import io
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "acceptance_gate_result_artifact.py"
SPEC = spec_from_file_location("acceptance_gate_result_artifact", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_bucket_status_maps_pass_fail_missing() -> None:
    bucket = MODULE._bucket_status(
        {
            "acceptance toolchain self-check (minimal regression)": "ok",
            "mcp health summary": "fail",
        },
        (
            "acceptance toolchain self-check (minimal regression)",
            "mcp health summary",
            "api health contract",
        ),
    )
    assert bucket == {
        "acceptance toolchain self-check (minimal regression)": "pass",
        "mcp health summary": "fail",
        "api health contract": "missing",
    }


def test_main_writes_release_matrix_artifact(tmp_path: Path, monkeypatch, capsys) -> None:
    out = tmp_path / "gate-latest.json"
    stdin = (
        "acceptance toolchain self-check (minimal regression)\tok\n"
        "mcp health summary\tok\n"
        "ops status health (project)\tok\n"
        "api health contract\tok\n"
        "api ops status contract\tok\n"
        "api telegram bridge status contract\tok\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    monkeypatch.setattr(
        "sys.argv",
        [
            "acceptance_gate_result_artifact.py",
            "--output",
            str(out),
            "--project-id",
            "default",
            "--ok",
            "6",
            "--failed",
            "0",
        ],
    )

    rc = MODULE.main()
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["release_matrix"]["status"] == "pass"
    assert payload["release_matrix"]["must_failed"] == 0
    assert payload["release_matrix"]["must_missing"] == 0
    assert "wrote gate artifact" in capsys.readouterr().out
