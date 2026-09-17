"""AnomalyDetector — M-of-N sliding window over a batch's reason codes."""

from app.batch.anomaly import AnomalyAdvisory, AnomalyDetector


def test_detector_constructs_with_default_thresholds():
    det = AnomalyDetector()
    assert det.window_n == 10
    assert det.threshold_m == 5


def test_detector_does_not_fire_below_threshold():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    for _ in range(4):
        adv = det.observe("BRAND.NAME.MISMATCH")
        assert adv is None
    # 4 same-code observations < threshold 5 — no advisory


def test_detector_fires_when_m_of_last_n_share_a_reason_code():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    advisories: list[AnomalyAdvisory] = []
    # 5 same-code observations in a row — 5 of the last 5 share, advisory fires
    for _ in range(5):
        adv = det.observe("BRAND.NAME.MISMATCH")
        if adv is not None:
            advisories.append(adv)
    assert len(advisories) == 1
    assert advisories[0].reason_code == "BRAND.NAME.MISMATCH"
    assert advisories[0].count == 5
    assert advisories[0].window == 10
    assert advisories[0].advisory_id  # uuid4 string


def test_detector_does_not_fire_when_no_code_reaches_threshold():
    """Heterogeneous batch: no single code accumulates M=5 in any 10-obs window.
    With 4 As + 4 Bs + 2 Cs, each code peaks at count 4 < threshold 5 — detector
    must stay silent. Confirms the threshold is per-code, not per-window-fill."""
    det = AnomalyDetector(window_n=10, threshold_m=5)
    codes = ["A", "B", "C", "A", "B", "A", "B", "C", "A", "B"]  # 4A 4B 2C
    advisories = []
    for c in codes:
        adv = det.observe(c)
        if adv is not None:
            advisories.append(adv)
    assert advisories == []


def test_detector_fires_on_first_code_that_reaches_threshold_after_window_fills():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    # 5 mismatches followed by 5 unknowns. Window state at t=10:
    #   ["A"]*5 + ["B"]*5 — both at count 5. Advisory fires at observation 5
    #   (when "A" first reaches threshold), not at observation 10.
    advisories = []
    for c in ["A"] * 5 + ["B"] * 5:
        adv = det.observe(c)
        if adv is not None:
            advisories.append(adv)
    assert len(advisories) == 1
    assert advisories[0].reason_code == "A"


def test_detector_fires_at_most_once_per_window_filling():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    # Once we fire on "A" at observation 5, observations 6-10 are still "A"
    # — but the advisory has already fired. We should NOT re-fire.
    advisories = []
    for _ in range(10):
        adv = det.observe("A")
        if adv is not None:
            advisories.append(adv)
    assert len(advisories) == 1


def test_detector_dismiss_resets_window_and_re_arms():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    advisories = []
    for _ in range(5):
        adv = det.observe("A")
        if adv is not None:
            advisories.append(adv)
    assert len(advisories) == 1
    advisory_id = advisories[0].advisory_id

    # Dismiss — window clears, detector re-arms
    det.dismiss(advisory_id)

    advisories2 = []
    for _ in range(4):
        adv = det.observe("A")
        if adv is not None:
            advisories2.append(adv)
    assert advisories2 == []  # only 4 < threshold 5 after reset

    adv = det.observe("A")
    advisories2.append(adv) if adv else None
    assert len(advisories2) == 1  # 5th fires again


def test_detector_dismiss_with_wrong_advisory_id_is_idempotent_noop():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    for _ in range(5):
        det.observe("A")
    # Dismiss with bogus advisory id — must be noop
    det.dismiss("not-a-real-advisory-id")

    # Window should still be in fired state — observing more "A"s does NOT
    # produce a fresh advisory because the outstanding one was not dismissed.
    adv = det.observe("A")
    assert adv is None


def test_detector_observes_none_reason_code_does_not_count():
    det = AnomalyDetector(window_n=10, threshold_m=5)
    # `pass` and `not_applicable` outcomes carry None as the reason_code in
    # the recent_dispositions deque. None must not count toward any threshold.
    for _ in range(5):
        adv = det.observe(None)
        assert adv is None
