import os
import shutil
import subprocess
import sys
from pathlib import Path

# `python -m app.vision --use-recordings` replays committed OpenAI responses
# instead of calling out, and it finds the recording set by the name of the
# directory the label sits in. So the label this test reads is staged into a
# directory named for the set, rather than read from the corpus in place.
RECORDING_SET = "01-spirits-clean"
LABEL = Path("tests/fixtures/labels/26231001000662/front.jpg")


def test_cli_smoke_exits_zero_on_real_label(tmp_path: Path) -> None:
    staged_dir = tmp_path / RECORDING_SET
    staged_dir.mkdir()
    staged_label = staged_dir / "label.jpg"
    shutil.copyfile(LABEL, staged_label)

    result = subprocess.run(
        [sys.executable, "-m", "app.vision",
         "--label", str(staged_label),
         "--use-recordings"],
        capture_output=True,
        timeout=30,
        env={**os.environ, "OPENAI_API_KEY": "sk-test", "VISION_MODE": "cloud"},
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
