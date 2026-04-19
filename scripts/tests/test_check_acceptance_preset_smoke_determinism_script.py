from pathlib import Path


def test_preset_smoke_determinism_checker_has_required_assertions() -> None:
    script = Path("scripts/check_acceptance_preset_smoke_determinism.sh").read_text(encoding="utf-8")
    assert "mode=fast" in script
    assert "mode=strict" in script
    assert "mode=full-deep" in script
    assert "HIVE_ACCEPTANCE_ENFORCE_HISTORY=true" in script
    assert "[ok] acceptance preset smoke determinism is stable" in script
