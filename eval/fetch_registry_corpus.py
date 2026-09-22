"""Fetch the application record and every label image for a list of TTB IDs
from the Public COLA Registry.

The registry answers plain HTTP with a bot-defence challenge, so this drives a
real browser through the `agent-browser` CLI and fetches each image from inside
the record's own page, where the session cookie applies. One record at a time,
with a pause between records.

    python -m eval.fetch_registry_corpus --ids ids.txt --out eval/data/registry

For each ID it writes `<out>/<ttbid>/record.json` (the form's fields: brand,
fanciful name, class/type code and description, origin code, source,
beverage type, permit, applicant name and address, status, dates, and each
image's type and address) and one file per label image. An ID that already
has `record.json` is skipped, so a stopped run resumes where it stopped.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path

FORM_URL = (
    "https://www.ttbonline.gov/colasonline/viewColaDetails.do"
    "?action=publicFormDisplay&ttbid={ttbid}"
)

_READ_FORM = r"""
(() => {
  const txt = document.body.innerText;
  const between = (start, end) => {
    const i = txt.indexOf(start);
    if (i < 0) return null;
    const rest = txt.slice(i + start.length);
    const j = end ? rest.search(end) : -1;
    const body = (j < 0 ? rest : rest.slice(0, j));
    const lines = body.split('\n').map(s => s.trim()).filter(Boolean);
    return lines;
  };
  const first = (lines) => {
    if (!lines || !lines.length) return null;
    return /^\d+[a-z]?\.\s/.test(lines[0]) ? null : lines[0];
  };
  const boxes = Array.from(document.querySelectorAll('input[type=checkbox]')).map(i => i.checked);
  const nameBlock = between('USED ON LABEL (Required)', /\n\s*4\. SERIAL NUMBER/);
  const imgs = Array.from(document.querySelectorAll('img'))
    .filter(i => i.src.includes('publicViewAttachment'))
    .map(i => ({src: i.src, type: (i.alt || '').replace(/^Label Image:\s*/, ''),
                w: i.naturalWidth, h: i.naturalHeight}));
  const status = (txt.match(/THE STATUS IS ([A-Z ]+)\./) || [])[1] || null;
  return JSON.stringify({
    error: /An error has occurred in the system/.test(txt),
    ttbid: (location.search.match(/ttbid=(\d+)/) || [])[1] || null,
    class_type_code: (txt.match(/\bCT\b\s+(\d+)/) || [])[1] || null,
    origin_code: (txt.match(/\bOR\b\s+(\d+)/) || [])[1] || null,
    permit: first(between('(Required)\n', /\n\s*3\. SOURCE/)),
    source: boxes.length >= 2 ? (boxes[0] ? 'domestic' : (boxes[1] ? 'imported' : null)) : null,
    beverage_type: boxes.length >= 5
      ? (['wine', 'spirits', 'malt'].filter((_, k) => boxes[2 + k])[0] || null) : null,
    applicant_name_address: nameBlock,
    brand: first(between('6. BRAND NAME (Required)', null)),
    fanciful_name: first(between('7. FANCIFUL NAME (If any)', null)),
    appellation: first(between('11. WINE APPELLATION (If on label)', null)),
    blown_or_translations: between('APPEARING ON LABELS.', /\n\s*PART II/),
    date_of_application: first(between('16. DATE OF APPLICATION', null)),
    date_issued: first(between('19. DATE ISSUED', null)),
    status: status,
    class_type_description: first(between('CLASS/TYPE DESCRIPTION', null)),
    images: imgs,
  });
})()
"""


def _browser(*args: str, stdin: str | None = None, timeout: int = 60) -> str:
    proc = subprocess.run(
        ["agent-browser", *args], input=stdin, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(f"agent-browser {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout


def _eval(js: str, timeout: int = 60) -> str:
    lines = [
        ln
        for ln in _browser("eval", "--stdin", stdin=js, timeout=timeout).splitlines()
        if ln.strip()
    ]
    if not lines:
        raise RuntimeError("agent-browser eval returned nothing")
    last = lines[-1]
    return json.loads(last) if last.startswith('"') else last


def _fetch_image(url: str) -> bytes:
    js = f"""
(async () => {{
  const r = await fetch({json.dumps(url)}, {{credentials: 'include'}});
  if (!r.ok) return JSON.stringify({{error: 'http ' + r.status}});
  const bytes = new Uint8Array(await r.arrayBuffer());
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000)
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}})()
"""
    out = _eval(js, timeout=90)
    if out.startswith("{"):
        raise RuntimeError(f"image fetch failed: {out}")
    return base64.b64decode(out)


def _slug(image_type: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", image_type.lower()).strip("-") or "image"


def fetch_one(ttbid: str, out: Path, pause: float) -> dict:
    target = out / ttbid
    if (target / "record.json").exists():
        return {"ttbid": ttbid, "skipped": True}
    _browser("open", FORM_URL.format(ttbid=ttbid), timeout=60)
    _browser("wait", "--load", "networkidle", timeout=60)
    record = json.loads(_eval(_READ_FORM))
    if record.get("error") or record.get("ttbid") != ttbid:
        raise RuntimeError("registry returned an error page")

    target.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    for image in record["images"]:
        slug = _slug(image["type"])
        seen[slug] = seen.get(slug, 0) + 1
        name = slug if seen[slug] == 1 else f"{slug}-{seen[slug]}"
        path = target / f"{name}.jpg"
        path.write_bytes(_fetch_image(image["src"]))
        time.sleep(pause / 2)
        image["file"] = path.name

    record["form_url"] = FORM_URL.format(ttbid=ttbid)
    record["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (target / "record.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return {"ttbid": ttbid, "images": len(record["images"]), "status": record["status"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", type=Path, required=True, help="file with one TTB ID per line")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between records")
    args = parser.parse_args(argv)

    ids = [ln.strip() for ln in args.ids.read_text().splitlines() if ln.strip()]
    args.out.mkdir(parents=True, exist_ok=True)
    failures = args.out / "failures.jsonl"
    done = 0
    for n, ttbid in enumerate(ids, 1):
        try:
            result = fetch_one(ttbid, args.out, args.pause)
            done += 0 if result.get("skipped") else 1
            print(f"[{n}/{len(ids)}] {json.dumps(result)}", flush=True)
        except Exception as exc:  # one bad record must not stop the run
            print(f"[{n}/{len(ids)}] {ttbid} FAILED: {exc}", flush=True)
            with failures.open("a") as fh:
                fh.write(json.dumps({"ttbid": ttbid, "error": str(exc)}) + "\n")
        time.sleep(args.pause)
    print(f"fetched {done} new records", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
