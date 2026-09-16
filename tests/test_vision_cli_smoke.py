import subprocess
import sys
from pathlib import Path


def test_cli_smoke_exits_zero_on_synthetic_fixture():
    result = subprocess.run(
        [sys.executable, "-m", "app.vision",
         "--label", "fixtures/01-spirits-clean/label.png",
         "--use-recordings"],
        capture_output=True,
        timeout=30,
        env={**__import__("os").environ, "OPENAI_API_KEY": "sk-test", "VISION_MODE": "cloud"},
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"field_count: 7" in result.stdout


def test_cli_smoke_missing_fixture_exits_2():
    result = subprocess.run(
        [sys.executable, "-m", "app.vision", "--label", "/does/not/exist.png"],
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert b"label not found" in result.stderr.lower()
