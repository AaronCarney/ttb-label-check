from pathlib import Path


def test_runbook_has_all_timing_sections():
    content = Path("DEMO-RUNBOOK.md").read_text()
    for marker in ("T-30", "T-5", "T-1", "T-0"):
        assert marker in content, f"DEMO-RUNBOOK missing {marker} section"


def test_runbook_documents_failure_recovery():
    content = Path("DEMO-RUNBOOK.md").read_text()
    assert "Failure recovery" in content or "failure recovery" in content


def test_runbook_documents_six_stage_path():
    content = Path("DEMO-RUNBOOK.md").read_text()
    for marker in ("Stage 1", "Stage 2", "Stage 3", "Stage 4", "Stage 5", "Stage 6"):
        assert marker in content, f"DEMO-RUNBOOK missing {marker}"
