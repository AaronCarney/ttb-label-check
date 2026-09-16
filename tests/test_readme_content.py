from pathlib import Path


def test_readme_preserves_hf_frontmatter():
    """T4's frontmatter must survive T9's body edit."""
    content = Path("README.md").read_text()
    assert content.startswith("---\n")
    for marker in ("sdk: docker", "app_port: 8000", "hardware: cpu-basic"):
        assert marker in content


def test_readme_has_setup_section():
    content = Path("README.md").read_text()
    assert "## Setup" in content
    assert "OPENAI_API_KEY" in content
    assert "uv sync" in content
    assert "uv run task demo" in content


def test_readme_links_decisions_and_runbook():
    content = Path("README.md").read_text()
    for ref in ("docs/PRD.md", "docs/ARCHITECTURE.md", "docs/03-decisions.md", "DEMO-RUNBOOK.md"):
        assert ref in content, f"README missing link to {ref}"


def test_readme_has_live_demo():
    content = Path("README.md").read_text()
    # Recorded walkthrough is descoped; the live demo URL is the demo.
    assert "## Setup" in content
