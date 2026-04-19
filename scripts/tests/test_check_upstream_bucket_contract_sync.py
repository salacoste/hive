from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "check_upstream_bucket_contract_sync.py"
SPEC = spec_from_file_location("check_upstream_bucket_contract_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_extract_doc_buckets_parses_three_sections() -> None:
    text = """
### Bucket A: Low-Risk Docs/Meta Sync
- `README.md`

### Bucket B: Medium-Risk Runtime/Graph Changes
- `core/framework/graph/context.py`

### Bucket C: High-Risk Removals / Architecture Shift
- `core/framework/agents/queen/queen_memory.py`
"""
    buckets = MODULE.extract_doc_buckets(text)
    assert buckets["a"] == {"README.md"}
    assert buckets["b"] == {"core/framework/graph/context.py"}
    assert buckets["c"] == {"core/framework/agents/queen/queen_memory.py"}


def test_main_fails_on_contract_drift(tmp_path: Path, monkeypatch, capsys) -> None:
    doc = tmp_path / "inventory.md"
    doc.write_text(
        "### Bucket A: Low-Risk Docs/Meta Sync\n"
        "- `README.md`\n"
        "### Bucket B: Medium-Risk Runtime/Graph Changes\n"
        "- `core/framework/graph/context.py`\n"
        "### Bucket C: High-Risk Removals / Architecture Shift\n"
        "- `core/framework/agents/queen/queen_memory.py`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "INVENTORY_DOC", doc)
    rc = MODULE.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "contract drift" in out
