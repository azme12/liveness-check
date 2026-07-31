from liveness.ml.partner_format import build_identity_result_breakdown


def test_breakdown_scores_0_100():
    breakdown = build_identity_result_breakdown(
        {
            "facialSimilarityScore": 100,
            "livenessCheckScore": 100,
            "face_match_passed": True,
            "liveness_passed": True,
        },
        outcome="clear",
        face_detected=True,
    )
    assert breakdown["outcome"] == "clear"
    assert breakdown["breakdown"]["faceAnalysis"]["breakdown"]["facialSimilarityScore"] == 100
    assert breakdown["breakdown"]["authenticityAnalysis"]["breakdown"]["livenessCheckScore"] == 100
    assert breakdown["breakdown"]["faceAnalysis"]["facialSimilarity"] == "clear"
