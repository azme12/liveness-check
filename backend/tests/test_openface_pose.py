import math

from liveness.ml.openface import HeadPoseLimits, OpenFaceAnalyzer, evaluate_head_pose, get_openface_analyzer


def test_openface_converts_radians_to_degrees():
    assert OpenFaceAnalyzer._pose_degrees(0.0) == 0.0
    assert abs(OpenFaceAnalyzer._pose_degrees(math.radians(25.0)) - 25.0) < 0.01
    assert OpenFaceAnalyzer._pose_degrees(30.0) == 30.0


def test_evaluate_head_pose_rejects_yaw():
    limits = HeadPoseLimits(max_yaw=20.0, max_pitch=15.0, max_roll=12.0, min_certainty=0.5)
    assert evaluate_head_pose(yaw=10.0, pitch=0.0, roll=0.0, certainty=0.8, limits=limits)
    assert not evaluate_head_pose(yaw=25.0, pitch=0.0, roll=0.0, certainty=0.8, limits=limits)


def test_evaluate_head_pose_rejects_roll():
    limits = HeadPoseLimits(max_yaw=20.0, max_pitch=15.0, max_roll=12.0, min_certainty=0.5)
    assert not evaluate_head_pose(yaw=0.0, pitch=0.0, roll=18.0, certainty=0.8, limits=limits)


def test_openface_opencv_fallback():
    import numpy as np

    img = np.full((480, 640, 3), 180, dtype=np.uint8)
    report = get_openface_analyzer().analyze(img, face_bbox=(160, 120, 320, 320))
    assert report.backend in {"opencv_pose_fallback", "insightface_pose", "openface_cli"}
    assert report.detection_certainty is not None


def test_selfie_profile_includes_head_pose_check():
    import numpy as np

    from liveness.ml.selfie_profile import validate_selfie_profile

    blank = np.full((480, 640, 3), 180, dtype=np.uint8)
    report = validate_selfie_profile(blank)
    assert "head_pose" not in report.checks or report.checks.get("head_pose") is False
