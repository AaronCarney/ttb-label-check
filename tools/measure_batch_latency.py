"""Measure the two numbers a reviewer feels: one check alone, and one label inside a batch.

Run against a service that is already up, from the repository root:

    uv run python -m tools.measure_batch_latency --url http://127.0.0.1:8123 --labels 8

The service has to be running under the shape it is being measured for. The
deployed service is 4 vCPU with `OCR_NUM_THREADS=4`, reading one image at a time
(`README.md`), so a local run that is going to be read against it is started the
same way:

    OCR_NUM_THREADS=4 nice -n 19 taskset -c 0-3 uv run uvicorn app.main:app --port 8123

**The two numbers.** They are different questions and they need different runs.
*Alone* is what a reviewer waits for after pressing check on one label: one
submission, both faces, nothing else in the service. *Inside a batch* is what
each label costs when many were sent together, which is not the same number —
the reviewer waits once for the first result and then reads while the rest
arrive, so what matters is the gap between results as much as the total.

**Both are measured from the stream, not from the batch snapshot.** The page
learns a result is ready when `/batches/{id}/stream` delivers its `label-result`
event (`app/batch/worker.py`), so that event's arrival is the wait, and polling
would only add its own interval to it. The bus replays events broadcast before a
reader attached, so nothing is lost by subscribing just after the POST; an event
that was already waiting is marked `replayed` rather than timed, because its
arrival time here is when this tool got round to reading it.

**What the submission is.** The sample pack the product offers a reviewer —
`GET /batches/sample.zip` — so the measurement sends what the page sends and not
a shape invented for it. The whole pack is fetched and the first N labels by TTB
ID are measured, because the route draws its `n` at random and two runs asking
for twelve would otherwise read two different twelves.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx


def _sample_pack(client: httpx.Client) -> tuple[list[tuple[str, bytes]], bytes]:
    """Every sample label the build ships, and the application rows filed for them.

    The whole pack, not the `n` that is going to be measured: the route draws
    its `n` with `random.sample` (`app/api/ui/samples.py`), so asking it for
    twelve twice gives two different twelves, and two runs then differ by which
    labels they read as well as by the machine. The caller takes a fixed set out
    of this.
    """
    response = client.get("/batches/sample.zip", params={"n": 10_000}, timeout=300.0)
    response.raise_for_status()
    images: list[tuple[str, bytes]] = []
    applications = b""
    with zipfile.ZipFile(io.BytesIO(response.content)) as pack:
        for name in sorted(pack.namelist()):
            if name.endswith(".csv"):
                applications = pack.read(name)
            elif name.endswith((".jpg", ".jpeg", ".png")):
                images.append((name, pack.read(name)))
    if not images:
        raise SystemExit("the sample pack carried no images")
    return images, applications


def _by_label(images: list[tuple[str, bytes]]) -> dict[str, list[tuple[str, bytes]]]:
    """The pack's images grouped by the label each face belongs to."""
    grouped: dict[str, list[tuple[str, bytes]]] = {}
    for name, data in images:
        stem = Path(name).stem
        label = stem.rsplit("-", 1)[0] if stem.rsplit("-", 1)[-1] in ("front", "back") else stem
        grouped.setdefault(label, []).append((name, data))
    return grouped


def _submit(
    client: httpx.Client, faces: list[tuple[str, bytes]], applications: bytes
) -> tuple[str, float]:
    """POST one submission. Returns its batch id and the moment the clock starts.

    The clock starts before the request goes out, because uploading is part of
    what the reviewer waits through.
    """
    files = [("labels", (name, data, "image/jpeg")) for name, data in faces]
    if applications:
        files.append(("applications", ("applications.csv", applications, "text/csv")))
    started = time.monotonic()
    response = client.post("/", files=files, follow_redirects=False, timeout=120.0)
    if response.status_code != 303:
        raise SystemExit(f"POST / answered {response.status_code}, expected 303")
    return response.headers["location"].rsplit("/", 1)[-1], started


def _faces_read(envelope: dict) -> int:
    """How many faces the reader got through on this label.

    The envelope carries no count, so it is taken from the faces the evidence
    was read off. It matters to a timing run because a face the quality gate
    refuses stops the label (`app/vision/local.py`), and a label that stopped
    after one face is a fast result for a reason that has nothing to do with
    speed.
    """
    tags = {
        evidence.get("face_tag")
        for field in envelope.get("fields") or []
        for evidence in [field.get("evidence") or {}]
        if evidence.get("face_tag")
    }
    return len(tags)


def _watch(client: httpx.Client, batch_id: str, started: float, expected: int) -> list[dict]:
    """Every `label-result` the stream delivers, with the wait that preceded it.

    `seconds` is measured from before the POST, so it is the whole of what the
    reviewer waited: the upload, the queue, the read and the rules.
    """
    attached = time.monotonic()
    results: list[dict] = []
    with client.stream("GET", f"/batches/{batch_id}/stream", timeout=600.0) as stream:
        event = ""
        for line in stream.iter_lines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                if event == "stream-end":
                    break
            elif line.startswith("data:") and event == "label-result":
                arrived = time.monotonic()
                payload = json.loads(line.split(":", 1)[1].strip())
                envelope = payload["envelope"]
                metrics = envelope.get("metrics") or {}
                results.append(
                    {
                        "label_ref": envelope.get("label_ref"),
                        "queue_position": payload.get("queue_position"),
                        "seconds": round(arrived - started, 3),
                        "replayed": arrived - attached < 0.05 and len(results) > 0,
                        "disposition": envelope.get("disposition"),
                        "total_duration_ms": metrics.get("total_duration_ms"),
                        "vision_duration_ms": metrics.get("vision_duration_ms"),
                        "cache_hit": metrics.get("cache_hit"),
                        "faces_read": _faces_read(envelope),
                    }
                )
                if len(results) >= expected:
                    break
    return results


def _gaps(results: list[dict]) -> list[float]:
    """How long the reviewer waited between one result and the next."""
    ordered = sorted(r["seconds"] for r in results)
    return [round(ordered[i] - ordered[i - 1], 3) for i in range(1, len(ordered))]


def _summary(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        "n": len(values),
        "median": round(statistics.median(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8123")
    parser.add_argument("--labels", type=int, default=8)
    parser.add_argument(
        "--pause",
        type=float,
        default=2.0,
        help="seconds between single submissions, so one check does not land on the last one",
    )
    parser.add_argument("--out", default="", help="where to write the run; stdout if unset")
    parser.add_argument("--note", default="", help="recorded with the run")
    args = parser.parse_args(argv)

    client = httpx.Client(base_url=args.url)
    # `/api/health`, not `/healthz`: Cloud Run's own front end answers
    # `/healthz` before the request reaches the container, so a run against
    # the deployed service gets the platform's 404 page rather than this
    # service's readiness (`app/api/healthz.py` says so where it registers
    # both paths). The container serves both, so this works locally too.
    health = client.get("/api/health", timeout=60.0).json()
    images, applications = _sample_pack(client)
    # The first N by TTB ID, so a second run reads the same labels as the first
    # and the difference between them is the machine.
    grouped = dict(sorted(_by_label(images).items())[: args.labels])
    faces_sent = sum(len(f) for f in grouped.values())
    print(f"{len(grouped)} labels, {faces_sent} images", file=sys.stderr)

    run = {
        "measured_at": datetime.now(UTC).isoformat(),
        "url": args.url,
        "note": args.note,
        "healthz": health,
        "labels": sorted(grouped),
        "alone": {"rows": []},
        "batch": {},
    }

    # One check at a time, which is the wait the five-second requirement is about.
    for label, faces in sorted(grouped.items()):
        batch_id, started = _submit(client, faces, applications)
        (result,) = _watch(client, batch_id, started, expected=1)
        result["label"] = label
        result["faces_sent"] = len(faces)
        run["alone"]["rows"].append(result)
        print(f"alone {label}: {result['seconds']}s ({len(faces)} faces)", file=sys.stderr)
        time.sleep(args.pause)

    run["alone"]["seconds"] = _summary([r["seconds"] for r in run["alone"]["rows"]])
    run["alone"]["by_faces"] = {
        str(k): _summary([r["seconds"] for r in run["alone"]["rows"] if r["faces_sent"] == k])
        for k in sorted({r["faces_sent"] for r in run["alone"]["rows"]})
    }

    # Every label in one submission, which is the wait a reviewer with a morning's
    # work in front of them actually has.
    all_faces = [face for _, faces in sorted(grouped.items()) for face in faces]
    batch_id, started = _submit(client, all_faces, applications)
    rows = _watch(client, batch_id, started, expected=len(grouped))
    total = max(r["seconds"] for r in rows)
    run["batch"] = {
        "batch_id": batch_id,
        "labels": len(grouped),
        "images": len(all_faces),
        "rows": rows,
        "first_result_seconds": round(min(r["seconds"] for r in rows), 3),
        "last_result_seconds": round(total, 3),
        "seconds_per_label": round(total / len(grouped), 3),
        "gap_between_results": _summary(_gaps(rows)),
        "engine_total_duration_ms": _summary(
            [float(r["total_duration_ms"]) for r in rows if r["total_duration_ms"] is not None]
        ),
    }
    print(
        f"batch: first {run['batch']['first_result_seconds']}s, "
        f"last {run['batch']['last_result_seconds']}s, "
        f"{run['batch']['seconds_per_label']}s per label",
        file=sys.stderr,
    )

    text = json.dumps(run, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
