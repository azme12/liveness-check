"""Tests for MiniFAS class mapping, fraud score, challenges, device fingerprint."""

from __future__ import annotations

import numpy as np

from liveness.ml.active_challenge import evaluate_challenge, needs_active_challenge
from liveness.ml.device_intel import build_fingerprint
from liveness.ml.document_authenticity import assess_document_authenticity
from liveness.ml.face_mesh import get_face_mesh_analyzer
from liveness.ml.fraud import compute_fraud_score
from liveness.ml.liveness import LivenessDetector
from liveness.ml.ocr import _mrz_checksum_ok
from liveness.ml.replay import analyze_replay_cues
from liveness.types import CheckOutcome


def test_minifas_three_class_uses_index_one_as_live(monkeypatch, tmp_path):
    class FakeSession:
        def get_inputs(self):
            return [type("I", (), {"name": "input"})()]

        def run(self, *_a, **_k):
            return [np.array([[1.0, 5.0, 0.5]], dtype=np.float32)]

    det = LivenessDetector.__new__(LivenessDetector)
    det.threshold = 0.5
    det.model_path = tmp_path / "missing.onnx"
    det._session = FakeSession()
    det._backend = "minifas_onnx"

    img = np.full((240, 240, 3), 120, dtype=np.uint8)
    report = det.predict(img, (40, 40, 160, 160))
    assert report.backend == "minifas_onnx"
    assert report.label == "live"
    assert report.score > 0.8
    assert report.details["live_score"] == report.score


def test_minifas_unavailable_returns_unknown(tmp_path):
    det = LivenessDetector.__new__(LivenessDetector)
    det.threshold = 0.5
    det.model_path = tmp_path / "missing.onnx"
    det._session = None
    det._backend = "unavailable"
    img = np.full((240, 240, 3), 120, dtype=np.uint8)
    report = det.predict(img)
    assert report.label == "unknown"
    assert report.backend == "unavailable"


def test_fraud_score_duplicate_and_clear():
    clear = compute_fraud_score(
        face_match_score=0.92,
        face_match_passed=True,
        liveness_score=0.88,
        liveness_passed=True,
        document_quality=0.9,
        document_valid=True,
        duplicate_hit=False,
        device_risk=10.0,
        velocity_count=0,
    )
    assert clear.outcome == CheckOutcome.CLEAR
    assert clear.risk_score < 35

    dup = compute_fraud_score(
        face_match_score=0.90,
        face_match_passed=True,
        liveness_score=0.85,
        liveness_passed=True,
        document_quality=0.9,
        document_valid=True,
        duplicate_hit=True,
        duplicate_score=0.82,
    )
    assert dup.outcome in {CheckOutcome.CONSIDER, CheckOutcome.REJECT}
    assert "duplicate_identity" in dup.flags


def test_needs_active_challenge_borderline():
    assert needs_active_challenge(liveness_score=0.55, liveness_threshold=0.5, liveness_backend="minifas_onnx")
    assert not needs_active_challenge(liveness_score=0.85, liveness_threshold=0.5, liveness_backend="minifas_onnx")
    assert needs_active_challenge(liveness_score=0.9, liveness_threshold=0.5, liveness_backend="unavailable")


def test_evaluate_blink_from_frames():
    frames = [{"ear": 0.28}, {"ear": 0.12}, {"ear": 0.26}]
    result = evaluate_challenge(challenge="blink", mesh=None, frames=frames)
    assert result.passed is True


def test_device_fingerprint_stable():
    a = build_fingerprint(ip="1.2.3.4", user_agent="Mozilla/5.0", client_hints={"platform": "Linux"})
    b = build_fingerprint(ip="1.2.3.4", user_agent="Mozilla/5.0", client_hints={"platform": "Linux"})
    c = build_fingerprint(ip="9.9.9.9", user_agent="Mozilla/5.0", client_hints={"platform": "Linux"})
    assert a.fingerprint_hash == b.fingerprint_hash
    assert a.fingerprint_hash != c.fingerprint_hash


def test_face_mesh_reports_production_backend():
    img = np.full((480, 640, 3), 180, dtype=np.uint8)
    report = get_face_mesh_analyzer().analyze(img, face_bbox=(160, 120, 320, 320))
    assert report.backend in {"mediapipe_solutions", "mediapipe_tasks", "unavailable"}


def test_replay_cues_score_range():
    img = np.full((480, 640, 3), 100, dtype=np.uint8)
    img[:6, :] = 10
    img[-6:, :] = 10
    sig = analyze_replay_cues(img, (100, 80, 200, 200))
    assert 0 <= sig.risk <= 100


def test_td3_mrz_real_check_digits():
    valid = [
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
    ]
    assert _mrz_checksum_ok(valid) is True
    invalid = [valid[0], valid[1][:-1] + "1"]
    assert _mrz_checksum_ok(invalid) is False


def test_document_authenticity_is_explainable():
    image = np.full((600, 900, 3), 180, dtype=np.uint8)
    cv2 = __import__("cv2")
    cv2.rectangle(image, (40, 40), (860, 560), (20, 20, 20), 4)
    cv2.putText(image, "NATIONAL ID", (100, 140), cv2.FONT_HERSHEY_SIMPLEX, 2, (20, 20, 20), 3)
    report = assess_document_authenticity(image)
    assert 0 <= report.score <= 1
    assert report.details["policy"] == "review_signal_only"
