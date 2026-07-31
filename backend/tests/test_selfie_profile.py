import numpy as np

from liveness.ml.selfie_profile import validate_selfie_profile


def test_selfie_profile_rejects_blank():
    blank = np.full((480, 640, 3), 180, dtype=np.uint8)
    report = validate_selfie_profile(blank)
    assert report.passed is False
    assert "no_face" in report.issues


def test_selfie_profile_messages_for_failures():
    blank = np.zeros((400, 400, 3), dtype=np.uint8)
    report = validate_selfie_profile(blank)
    assert not report.passed
    assert len(report.messages) >= 1
