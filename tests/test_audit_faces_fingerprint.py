"""What "the same submission" means once a label has more than one face.

`faces_fingerprint` is the bytes both the audit trail's `input_hash` and the
evaluator's result-cache key are taken over. Two submissions that share a
fingerprint are treated as the same submission: the cache hands the second one
the first one's answer, and the audit trail records them under one input. So
anything that changes the answer has to change the fingerprint.
"""

from __future__ import annotations

from app.schemas.application import Application
from app.schemas.label import Dimensions, Face, Label
from app.services.audit import _input_hash, faces_fingerprint

_PNG = b"\x89PNG\r\n\x1a\n"


def _face(image_bytes: bytes = _PNG, *, face_tag: str = "front", dimensions=None) -> Face:
    return Face(
        image_bytes=image_bytes,
        content_type="image/png",
        face_tag=face_tag,
        dimensions=dimensions,
    )


def _label(*faces: Face) -> Label:
    return Label(label_id="L-001", batch_id="B-001", faces=faces)


def test_the_same_faces_fingerprint_the_same():
    assert faces_fingerprint(_label(_face(b"front"), _face(b"back", face_tag="back"))) == (
        faces_fingerprint(_label(_face(b"front"), _face(b"back", face_tag="back")))
    )


def test_sending_a_back_face_is_a_different_submission():
    """The case the whole multi-face change turns on. Front alone and front
    plus back get different answers, so they must not share a cache entry."""
    front_only = faces_fingerprint(_label(_face(b"front")))
    both = faces_fingerprint(_label(_face(b"front"), _face(b"back", face_tag="back")))
    assert front_only != both


def test_where_one_face_ends_and_the_next_begins_counts():
    """A plain concatenation cannot tell these apart: `b"ab" + b"c"` and
    `b"a" + b"bc"` are the same bytes. They are different submissions — a
    different pair of photographs — and the reader gives different answers."""
    split_one = faces_fingerprint(_label(_face(b"ab"), _face(b"c", face_tag="back")))
    split_two = faces_fingerprint(_label(_face(b"a"), _face(b"bc", face_tag="back")))
    assert split_one != split_two


def test_which_face_a_photograph_was_submitted_as_counts():
    """Every observation now carries the face it was read from, so the same
    photograph filed as a front and as a back produces different evidence."""
    as_front = faces_fingerprint(_label(_face(b"same-image", face_tag="front")))
    as_back = faces_fingerprint(_label(_face(b"same-image", face_tag="back")))
    assert as_front != as_back


def test_face_order_counts():
    front, back = _face(b"front"), _face(b"back", face_tag="back")
    assert faces_fingerprint(_label(front, back)) != faces_fingerprint(_label(back, front))


def test_declared_dimensions_count():
    """The applicant's declared DPI is the last source the quality report
    falls back to, so it can change the answer."""
    plain = faces_fingerprint(_label(_face()))
    declared = faces_fingerprint(
        _label(_face(dimensions=Dimensions(width_px=200, height_px=200, dpi=300)))
    )
    assert plain != declared


def test_input_hash_separates_the_same_submissions_the_fingerprint_does():
    """The audit trail inherits all of it, because `input_hash` is taken over
    the application plus this fingerprint."""
    app = Application(application_id="A-001", evaluation_id="EV-001")
    front_only = _input_hash(app, _label(_face(b"front")))
    both = _input_hash(app, _label(_face(b"front"), _face(b"back", face_tag="back")))
    assert front_only != both
