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


def test_face_authentication_with_gallery_match():
    engine = CheckEngine()
    img = _blank_bgr()
    result = engine.run(
        CheckType.FACE_AUTHENTICATION,
        CheckContext(
            live_photo_image=img,
            options={
                "gallery_match": {
                    "label": "Jane",
                    "score": 0.92,
                    "passed": True,
                    "embedding_id": "femb_test",
                    "backend": "histogram",
                }
            },
        ),
    )
    assert result.outcome in {CheckOutcome.CLEAR, CheckOutcome.REJECT}
    assert result.biometric is not None


def test_face_authentication_no_enrollment():
    engine = CheckEngine()
    img = _blank_bgr()
    result = engine.run(
        CheckType.FACE_AUTHENTICATION,
        CheckContext(
            live_photo_image=img,
            options={"gallery_error": "no_enrollment"},
        ),
    )
    assert result.outcome == CheckOutcome.REJECT
    assert "no_face_enrollment" in result.explainability


def test_openface_opencv_fallback():
    from liveness.ml.openface import OpenFaceAnalyzer

    img = _blank_bgr()
    report = OpenFaceAnalyzer().analyze(img, face_bbox=(160, 120, 320, 320))
    assert report.backend == "opencv_pose_fallback"
    assert report.detection_certainty is not None


def test_identity_check_respects_document_type_hint():
    engine = CheckEngine()
    img = _blank_bgr()
    result = engine.run(
        CheckType.IDENTITY,
        CheckContext(
            document_image=img,
            live_photo_image=img,
            options={"document_type": "fayda"},
        ),
    )
    assert result.document is not None
    assert result.document.document_type == "fayda"
    assert result.signals is not None
    scores = result.signals.get("scores") or {}
    assert scores.get("document_type") == "fayda"
    assert "face_match_score" in scores
