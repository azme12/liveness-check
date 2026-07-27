"""Core library unit tests (no server)."""

from __future__ import annotations

import numpy as np

from liveness.checks import CheckContext, CheckEngine
from liveness.ml.quality import assess_quality
from liveness.types import CheckOutcome, CheckType


def _blank_bgr(h=480, w=640, color=(180, 160, 140)):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = color
    # Add texture so Laplacian blur score is not zero
    noise = np.random.randint(0, 40, (h, w, 3), dtype=np.uint8)
    return cv2_add(img, noise)


def cv2_add(a, b):
    import cv2

    return cv2.add(a, b)


def test_quality_scores_image():
    img = _blank_bgr()
    report = assess_quality(img)
    assert 0.0 <= report.score <= 1.0


def test_document_check_rejects_tiny_image():
    engine = CheckEngine()
    tiny = np.zeros((50, 50, 3), dtype=np.uint8)
    result = engine.run(CheckType.DOCUMENT, CheckContext(document_image=tiny))
    assert result.outcome == CheckOutcome.REJECT
    assert result.document is not None


def test_identity_check_missing_selfie():
    engine = CheckEngine()
    img = _blank_bgr()
    result = engine.run(
        CheckType.IDENTITY,
        CheckContext(document_image=img, live_photo_image=None),
    )
    assert result.outcome == CheckOutcome.REJECT


def test_screening_clear():
    engine = CheckEngine()
    result = engine.run(
        CheckType.STANDARD_SCREENING,
        CheckContext(client_name="Jane Doe"),
    )
    assert result.outcome == CheckOutcome.CLEAR
