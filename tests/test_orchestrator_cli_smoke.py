import os
import subprocess
import sys


def test_cli_smoke_exits_zero_on_recordings():
    env = {**os.environ, "OPENAI_API_KEY": "sk-test", "ORCHESTRATOR_BACKEND": "openai"}
    result = subprocess.run(
        [sys.executable, "-m", "app.orchestrator",
         "--task", "brand_disambig",
         "--fixture", "01-spirits-clean",
         "--backend", "openai",
         "--use-recordings"],
        capture_output=True, timeout=30, env=env,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"task: brand_disambig" in result.stdout
    assert b"decision:" in result.stdout


def test_cli_smoke_missing_recording_exits_2():
    env = {**os.environ, "OPENAI_API_KEY": "sk-test", "ORCHESTRATOR_BACKEND": "openai"}
    result = subprocess.run(
        [sys.executable, "-m", "app.orchestrator",
         "--task", "brand_disambig",
         "--fixture", "99-does-not-exist",
         "--backend", "openai",
         "--use-recordings"],
        capture_output=True, timeout=10, env=env,
    )
    assert result.returncode == 2
    assert b"recording not found" in result.stderr.lower()


def test_cli_smoke_bad_backend_exits_2():
    result = subprocess.run(
        [sys.executable, "-m", "app.orchestrator",
         "--task", "brand_disambig", "--fixture", "01-spirits-clean",
         "--backend", "vllm"],
        capture_output=True, timeout=10,
    )
    assert result.returncode == 2
