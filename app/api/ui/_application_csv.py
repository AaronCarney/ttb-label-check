"""The applications a batch of labels is checked against, as one CSV.

A label means nothing on its own: the check is the label against the
application filed for it. The single-label page asks for that application in
ten form fields, which works for one label and not for three hundred. This is
the same ten fields, one row per label, joined to the images by filename.

**Why a CSV and not the JSON `POST /batches` already takes.** That envelope is
right for a machine and wrong for a person: a reviewer holding 300 filings has
them in a spreadsheet, and a spreadsheet writes CSV. The alternative of a
sidecar file per label was rejected for multiplying the file count the form
already caps at `limits.MAX_BATCH_FILES`. The brief bars integration with COLAs
Online (C-1), so a file the reviewer supplies is the honest stand-in for the
feed a real deployment would read from the system of record.

**The join is the filename**, the same stem `app/api/ui/_faces.py` reads to
decide which two files are two faces of one label. A row's `filename` may carry
an image extension or not, and may name either face; all of them reduce to the
same key. A label with no row is not an error — it runs the label-only rules
and says so, which is the behaviour a bulk upload had before this file existed.

**A duplicate filename is refused rather than resolved.** Two rows for one
label means the reviewer's sheet is wrong, and picking one of them silently
compares a label against an application that was never filed for it. That is
the one failure this file exists to prevent, so it is not made quietly.
"""

from __future__ import annotations

import csv
import io

# The join key, then the ten fields the application form posts, in the order
# the form asks for them. Anything else in the sheet is ignored: a reviewer's
# export carries columns of their own, and refusing it for them would make the
# real path the one nobody can use.
FILENAME_COLUMN = "filename"
APPLICATION_FIELDS: tuple[str, ...] = (
    "beverage_type",
    "brand_name",
    "fanciful_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "applicant_name_address",
    "source_of_product",
    "origin",
    "wine_appellation",
)
COLUMNS: tuple[str, ...] = (FILENAME_COLUMN, *APPLICATION_FIELDS)

# What a row's `filename` may end in and still name the same label. The stem is
# what joins, so `26230001000420`, `26230001000420-front.jpg` and
# `26230001000420.JPG` are one key.
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
_FACE_SUFFIXES = ("-front", "-back")


class ApplicationCsvError(ValueError):
    """The applications file cannot be read. The message is shown to the user."""


def key_for(name: str) -> str:
    """The join key one filename reduces to.

    Case is folded and an image extension dropped, then a `-front`/`-back`
    suffix, so a row naming either face of a label joins the label both faces
    make up.
    """
    key = name.strip().casefold()
    for extension in _IMAGE_EXTENSIONS:
        if key.endswith(extension):
            key = key[: -len(extension)]
            break
    for suffix in _FACE_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def render(rows: list[dict[str, str]]) -> str:
    """The CSV text for `rows`, one row per label, with a header line.

    Every column is written even where a row leaves it blank, because a blank
    cell under a named heading tells a reviewer the application declared
    nothing for that element — which is a fact the check reports — while a
    missing column tells them only that the file is short.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS), lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    return buffer.getvalue()


def parse(body: bytes) -> dict[str, dict[str, str]]:
    """The applications one uploaded CSV declares, keyed by `key_for` filename.

    Each value is the ten posted fields, ready for `_build_application`, with
    an absent column read as blank. Raises `ApplicationCsvError` with a message
    a reviewer can act on.
    """
    try:
        # `utf-8-sig` because a spreadsheet writes a byte-order mark, and a
        # first column read as `﻿filename` would make every row miss.
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ApplicationCsvError(
            "The applications file is not UTF-8 text. Save it from your "
            "spreadsheet as CSV UTF-8 and upload it again."
        ) from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    headings = [name.strip().casefold() for name in (reader.fieldnames or [])]
    if FILENAME_COLUMN not in headings:
        raise ApplicationCsvError(
            f"The applications file has no {FILENAME_COLUMN!r} column, so there is "
            "nothing to join its rows to the images by. Its first line must name "
            f"the columns: {', '.join(COLUMNS)}."
        )

    table: dict[str, dict[str, str]] = {}
    seen: dict[str, str] = {}
    for line_number, raw in enumerate(reader, start=2):
        row = {
            (name or "").strip().casefold(): (value or "").strip()
            for name, value in raw.items()
            if name is not None
        }
        filename = row.get(FILENAME_COLUMN, "")
        if not filename and not any(row.get(field) for field in APPLICATION_FIELDS):
            # A blank line. Spreadsheets leave them at the end of a file and
            # they declare nothing, so they are not a fault to report.
            continue
        if not filename:
            raise ApplicationCsvError(
                f"Line {line_number} of the applications file declares an application "
                "but names no file, so there is no label to check it against."
            )
        key = key_for(filename)
        if key in seen:
            raise ApplicationCsvError(
                f"The applications file has two rows for {filename!r} "
                f"(line {seen[key]} and line {line_number}). One label cannot be "
                "checked against two applications — remove one of the rows."
            )
        seen[key] = str(line_number)
        table[key] = {field: row.get(field, "") for field in APPLICATION_FIELDS}
    return table
