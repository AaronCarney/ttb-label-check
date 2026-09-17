# tests/test_vision_isolation.py
"""Inference dependencies stay behind the reader's seam: only app/vision/ may
import openai, paddleocr, cv2 or torch.
The reader is the only place a hosted model may be reached from."""
import re
from pathlib import Path

FORBIDDEN_OUTSIDE_VISION = (
    re.compile(r"\bimport\s+openai\b"),
    re.compile(r"\bfrom\s+openai\b"),
    re.compile(r"\bimport\s+paddleocr\b"),
    re.compile(r"\bfrom\s+paddleocr\b"),
    re.compile(r"\bimport\s+cv2\b"),
    re.compile(r"\bfrom\s+cv2\b"),
    re.compile(r"\bimport\s+torch\b"),
    re.compile(r"\bfrom\s+torch\b"),
)


def test_inference_deps_isolated_to_app_vision():
    violations: list[str] = []
    app_root = Path("app")
    for py in app_root.rglob("*.py"):
        if "app/vision/" in str(py):
            continue
        text = py.read_text()
        for rx in FORBIDDEN_OUTSIDE_VISION:
            for m in rx.finditer(text):
                violations.append(f"{py}: {m.group(0)}")
    assert not violations, "Inference deps leaked outside app/vision/:\n" + "\n".join(violations)


def test_florence_qwen_imports_absent_globally():
    """No local vision-model stack is imported anywhere: the app carries no
    Florence-2 or Qwen-VL dependency, and nothing that pulls one in."""
    forbidden = (
        re.compile(r"\bflorence"),
        re.compile(r"\bqwen"),
        re.compile(r"\btransformers\b"),
        re.compile(r"\baccelerate\b"),
        re.compile(r"\bbitsandbytes\b"),
    )
    violations: list[str] = []
    for py in Path("app").rglob("*.py"):
        text = py.read_text()
        for rx in forbidden:
            for m in rx.finditer(text):
                violations.append(f"{py}: {m.group(0)}")
    assert not violations, "forbidden imports detected:\n" + "\n".join(violations)
