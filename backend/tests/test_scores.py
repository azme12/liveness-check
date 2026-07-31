from liveness.ml.scores import enrich_verification_scores, score_to_percent


def test_score_to_percent():
    assert score_to_percent(0.0) == 0
    assert score_to_percent(1.0) == 100
    assert score_to_percent(0.845) == 84
    assert score_to_percent(None) is None


def test_enrich_verification_scores():
    out = enrich_verification_scores({"face_match_score": 0.92, "liveness_score": 0.6})
    assert out["facialSimilarityScore"] == 92
    assert out["livenessCheckScore"] == 60
