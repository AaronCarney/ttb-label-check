"""Measure what reading two images at once would buy, before anything is built to do it.

Run from the repository root, on the core count the service has:

    OCR_NUM_THREADS=4 nice -n 19 taskset -c 0-3 uv run python -m tools.measure_read_scaling

**The question.** A check of a two-faced label reads one face and then the
other, and a running copy reads one image at a time: it holds a single OCR
engine behind `_read_lock` (`app/vision/local.py`). Reading both faces at once
therefore means lifting that serialisation, not merely asking for both together
— a spike that issues two reads without lifting it measures the lock and
reports no improvement for the wrong reason.

**Why this runs in-process and not against the service.** What is being measured
is whether the cores have anything left to give, and that is a property of the
reader and the machine, not of the routes around them. Running it here also lets
the lock be lifted by calling `_read` instead of `_read_serialised`, which is
the change itself, without shipping the change to find out.

**The shapes.**

- `serial` at 1, 2 and 4 engine threads: one image at a time, the reader as it
  is. Comparing them says how much of the machine a single read already uses. If
  a one-thread read costs about four times a four-thread read, four cores are
  genuinely busy and there is nothing for a second read to use.
- `shared/K`: K images in flight through one engine with the lock lifted, which
  is the smallest possible version of the change.
- `perthread/K`: K images in flight, one engine each, the thread budget split
  between them. Safe against an engine that does not promise to be called from
  two threads at once, and what the change would have to become if the shared
  engine misbehaved.

`cores_busy` is CPU seconds over wall seconds: 4.0 means the run kept four cores
working for its whole duration, and nothing is left for concurrency to fill.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.vision.local import LocalVisionExtractor

CORPUS = Path("tests/fixtures/labels")


def _images(limit: int) -> list[tuple[str, bytes]]:
    """Faces from the corpus, fronts and backs alike, in a fixed order."""
    found: list[tuple[str, bytes]] = []
    for label in sorted(d for d in CORPUS.iterdir() if d.is_dir()):
        for face in ("front.jpg", "back.jpg"):
            path = label / face
            if path.is_file():
                found.append((f"{label.name}/{face}", path.read_bytes()))
    if not found:
        raise SystemExit(f"no images under {CORPUS}")
    return found[:limit]


def _reader(threads: int, warm_with: bytes) -> LocalVisionExtractor:
    """A loaded, warmed reader.

    Warmed because the first inference after a load optimises each graph and
    allocates its arenas, and that cost belongs to nobody's measurement.
    """
    reader = LocalVisionExtractor(
        settings=Settings(ocr_num_threads=threads), ring_buffer=deque(maxlen=64)
    )
    reader._load_once()
    reader._read(warm_with)
    return reader


def _cpu_seconds() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def _rss_mb() -> int:
    """What this process is holding now, not the peak it once held.

    `ru_maxrss` is a high-water mark and never comes down, so in a run that
    builds several engines it reports the same number for every shape after the
    largest one. The service has 4 GiB (`README.md`), and an engine per thread
    is the shape that could spend it, so the figure has to be one that can be
    read per shape.
    """
    for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
        if line.startswith("VmRSS:"):
            return round(int(line.split()[1]) / 1024)
    return 0


def _run(
    shape: str, readers: list[LocalVisionExtractor], workers: int, images: list[tuple[str, bytes]]
) -> dict:
    """Read every image once, `workers` at a time, round-robin over `readers`."""
    per_image: list[float] = []
    guard = threading.Lock()

    def one(index: int) -> None:
        _, data = images[index]
        start = time.monotonic()
        # `_read`, not `_read_serialised`: the lock is what this is measuring.
        readers[index % len(readers)]._read(data)
        taken = time.monotonic() - start
        with guard:
            per_image.append(taken)

    cpu_before, wall_before = _cpu_seconds(), time.monotonic()
    if workers == 1:
        for index in range(len(images)):
            one(index)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, range(len(images))))
    wall = time.monotonic() - wall_before
    cpu = _cpu_seconds() - cpu_before
    return {
        "shape": shape,
        "workers": workers,
        "engines": len(readers),
        "engine_threads": readers[0]._thread_cap(),
        "images": len(images),
        "wall_seconds": round(wall, 2),
        "seconds_per_image": round(wall / len(images), 3),
        "cpu_seconds": round(cpu, 1),
        "cores_busy": round(cpu / wall, 2),
        "slowest_image_seconds": round(max(per_image), 3),
        "median_image_seconds": round(statistics.median(per_image), 3),
        "rss_mb": _rss_mb(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=int, default=8, help="faces to read in each shape")
    parser.add_argument("--threads", type=int, default=4, help="the service's thread budget")
    parser.add_argument("--out", default="", help="where to write the run; stdout if unset")
    parser.add_argument("--note", default="")
    parser.add_argument(
        "--only",
        default="",
        help=(
            "run one shape and stop, so the memory it holds is its own. Every engine "
            "a run builds stays built, so a shape measured after others reports their "
            "memory as well as its own. Matches on any part of a shape name."
        ),
    )
    args = parser.parse_args(argv)

    images = _images(args.images)
    cores = len(os.sched_getaffinity(0))
    run = {
        "measured_at": datetime.now(UTC).isoformat(),
        "note": args.note,
        "cores_available": cores,
        "thread_budget": args.threads,
        "images": [name for name, _ in images],
        "runs": [],
    }
    print(f"{len(images)} images on {cores} cores", file=sys.stderr)

    def record(row: dict) -> None:
        """Keep a shape's result, unless this run was asked for a different shape."""
        if args.only and args.only not in row["shape"]:
            return
        row["rss_mb_is_this_shape_alone"] = bool(args.only)
        run["runs"].append(row)
        print(json.dumps(row), file=sys.stderr)

    def wanted(shape: str) -> bool:
        """Whether a shape is worth building engines for in this run."""
        return not args.only or args.only in shape

    # How much of the machine one read already uses.
    for threads in sorted({1, 2, args.threads}):
        if not wanted(f"serial, {threads} engine threads"):
            continue
        reader = _reader(threads, images[0][1])
        record(_run(f"serial, {threads} engine threads", [reader], 1, images))
        del reader

    # The change itself, in its two possible forms, at the service's budget.
    if wanted("shared engine, 2 in flight") or wanted("serial again"):
        full = _reader(args.threads, images[0][1])
        record(_run("shared engine, 2 in flight", [full], 2, images))
        record(_run("serial again, for the drift between runs", [full], 1, images))
        del full

    # What a second engine costs to hold, measured where it is paid for: the
    # service has 4 GiB and an engine per thread is the shape that could spend it.
    if wanted("one engine per thread, 2 in flight"):
        split = max(1, args.threads // 2)
        before = _rss_mb()
        pair = [_reader(split, images[0][1]) for _ in range(2)]
        run["second_engine_rss_mb_at_build"] = _rss_mb() - before
        record(_run("one engine per thread, 2 in flight", pair, 2, images))
        del pair

    if wanted(f"one engine per thread, {args.threads} in flight"):
        singles = [_reader(1, images[0][1]) for _ in range(args.threads)]
        record(
            _run(f"one engine per thread, {args.threads} in flight", singles, args.threads, images)
        )
    run["rss_mb_peak"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)

    text = json.dumps(run, indent=1) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
