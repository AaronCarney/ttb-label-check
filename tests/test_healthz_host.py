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
        "processor\t: 0\nvendor_id\t: GenuineIntel\ncpu family\t: 6\nmodel\t\t: 85\n"
        "model name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\nstepping\t: 7\n\n"
        "processor\t: 1\nmodel name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n"
    )
    facts = healthz.host_facts(cpuinfo)
    assert facts["cpu_model"] == "Intel(R) Xeon(R) CPU @ 2.20GHz"
    assert facts["cpu_id"] == "GenuineIntel family 6 model 85 stepping 7"


def test_a_sandbox_that_hides_the_name_still_names_the_generation(tmp_path: Path) -> None:
    """Cloud Run's gVisor sandbox writes `model name: unknown`, but passes the
    vendor, family, model and stepping through, and those identify the
    processor generation."""
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text(
        "processor\t: 0\nvendor_id\t: AuthenticAMD\ncpu family\t: 25\nmodel\t\t: 1\n"
        "model name\t: unknown\nstepping\t: 1\n"
    )
    facts = healthz.host_facts(cpuinfo)
    assert facts["cpu_model"] == "unknown"
    assert facts["cpu_id"] == "AuthenticAMD family 25 model 1 stepping 1"


def test_an_unreadable_cpuinfo_reports_unknown(tmp_path: Path) -> None:
    """Unknown rather than a guess, the rule `version` and `commit` follow."""
    facts = healthz.host_facts(tmp_path / "absent")
    assert facts["cpu_model"] == "unknown"
    assert facts["cpu_id"] == "unknown"


def test_the_health_answer_carries_the_host(monkeypatch) -> None:
    monkeypatch.setitem(healthz._warmed, "done", True)
    response = asyncio.run(healthz.healthz(Settings()))
    host = json.loads(response.body)["host"]
    assert set(host) == {"cpu_model", "cpu_id", "cpus", "usable_cpus"}
