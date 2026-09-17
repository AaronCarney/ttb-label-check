import inspect

from app.vision.base import VisionExtractor


def test_protocol_runtime_checkable():
    # @runtime_checkable enables isinstance() against the Protocol.
    assert hasattr(VisionExtractor, "_is_runtime_protocol")


def test_protocol_attrs():
    attrs = set(VisionExtractor.__protocol_attrs__)
    assert "extract" in attrs
    assert "ensure_loaded" in attrs
    assert "warm" in attrs, (
        "`warm` is on the Protocol rather than reached through a getattr, so a "
        "reader that does not implement it is a type error at the seam instead "
        "of an AttributeError through /healthz and a silent 503"
    )


def test_extract_signature_async():
    extract = VisionExtractor.extract
    assert inspect.iscoroutinefunction(extract)


def test_ensure_loaded_signature_async():
    ensure_loaded = VisionExtractor.ensure_loaded
    assert inspect.iscoroutinefunction(ensure_loaded)


def test_warm_signature_async():
    warm = VisionExtractor.warm
    assert inspect.iscoroutinefunction(warm)
