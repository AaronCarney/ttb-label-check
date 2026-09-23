"""`/api/health` names the processor the service is running on.

A read's time depends on the processor under it, and Cloud Run does not say
which one an instance got. Decision 0066 could only infer that a slower live read
came from the host. With the processor in the health answer, and the live timing
record reading it, each timing carries the processor that produced it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.api import healthz
from app.config import Settings


def test_the_processor_model_is_read_from_cpuinfo(tmp_path: Path) -> None:
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\nvendor_id\t: GenuineIntel\n"
        "model name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n\n"
        "processor\t: 1\nmodel name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n"
    )
    assert healthz.host_facts(cpuinfo)["cpu_model"] == "Intel(R) Xeon(R) CPU @ 2.20GHz"


def test_an_unreadable_cpuinfo_reports_unknown(tmp_path: Path) -> None:
    """Unknown rather than a guess, the rule `version` and `commit` follow."""
    assert healthz.host_facts(tmp_path / "absent")["cpu_model"] == "unknown"


def test_the_health_answer_carries_the_host(monkeypatch) -> None:
    monkeypatch.setitem(healthz._warmed, "done", True)
    response = asyncio.run(healthz.healthz(Settings()))
    host = json.loads(response.body)["host"]
    assert set(host) == {"cpu_model", "cpus"}
