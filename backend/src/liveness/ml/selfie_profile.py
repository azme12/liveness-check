"""Strict live-selfie profile validation before ID↔selfie matching."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from liveness.config import get_settings
from liveness.ml.face import FaceAnalyzer, get_face_analyzer
from liveness.ml.openface import OpenFaceAnalyzer, get_openface_analyzer
from liveness.ml.quality import _to_bgr

ISSUE_MESSAGES: dict[str, str] = {
    "no_face": "No face detected. Face the camera directly.",
    "multiple_faces": "Multiple faces detected. Only you should be in the photo.",
    "face_too_small": "Move closer — your face must fill more of the frame.",
    "face_off_center": "Center your face in the frame.",
    "too_blurry": "Photo is too blurry. Hold steady and upload again.",
    "too_dark": "Too dark. Use brighter, even lighting.",
    "too_bright": "Too bright or overexposed.",
    "face_cropped": "Full face not visible. Keep forehead and chin in frame.",
    "glasses_detected": "Remove glasses and upload again.",
    "face_covered": "Face appears covered (mask, hand, or scarf). Show your full face.",
    "busy_background": "Use a plain background — avoid clutter behind you.",
    "glare": "Reduce glare or reflections on your face.",
    "low_quality": "Image quality too low. Retake the selfie.",
    "head_turned": "Face the camera directly — do not turn your head left or right.",
    "head_tilted_up": "Look straight ahead — do not look up.",
    "head_tilted_down": "Look straight ahead — do not look down.",
    "head_rolled": "Keep your head level — do not tilt sideways.",
    "head_pose_invalid": "Face the camera directly with a neutral, frontal pose.",
}


@dataclass
class SelfieProfileReport:
    passed: bool
    score: float
    issues: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "profile_status": "passed" if self.passed else "failed",
            "score": round(self.score, 3),
            "issues": self.issues,
            "messages": self.messages,
            "checks": self.checks,
        }


def _face_crop(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox
    H, W = image.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + w), min(H, y + h)
    crop = image[y1:y2, x1:x2]
    return crop if crop.size else image


def _detect_glasses(face_gray: np.ndarray) -> bool:
    """Heuristic: strong horizontal structure in the eye band."""
    fh, fw = face_gray.shape[:2]
    if fh < 40 or fw < 40:
        return False
    y0, y1 = int(fh * 0.22), int(fh * 0.48)
    band = face_gray[y0:y1, int(fw * 0.08) : int(fw * 0.92)]
    if band.size == 0:
        return False
    sx = cv2.Sobel(band, cv2.CV_64F, 1, 0, ksize=3)
    sy = cv2.Sobel(band, cv2.CV_64F, 0, 1, ksize=3)
    h_energy = float(np.mean(np.abs(sx)))
    v_energy = float(np.mean(np.abs(sy))) + 1e-6
    # Glasses frames / glare bands raise horizontal edges in the eye region.
    return h_energy / v_energy > 1.35 and h_energy > 18.0


def _detect_face_cover(face_gray: np.ndarray) -> bool:
    """Heuristic: unusually uniform lower face (mask/scarf/hand)."""
    fh, _ = face_gray.shape[:2]
    if fh < 50:
        return False
    lower = face_gray[int(fh * 0.55) :, :]
    upper = face_gray[int(fh * 0.15) : int(fh * 0.45), :]
    if lower.size == 0 or upper.size == 0:
        return False
    lower_std = float(np.std(lower))
    upper_std = float(np.std(upper))
    # Masked mouth/nose: lower region much smoother than eyes/nose bridge.
    return lower_std < 12.0 and upper_std > lower_std * 1.8


def _busy_background(image: np.ndarray, bbox: tuple[int, int, int, int]) -> bool:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    mask = np.ones((h, w), dtype=np.uint8) * 255
    x, y, bw, bh = bbox
    cx, cy = x + bw // 2, y + bh // 2
    axes = (int(bw * 0.65), int(bh * 0.72))
    cv2.ellipse(mask, (cx, cy), axes, 0, 0, 360, 0, -1)
    bg = gray[mask > 0]
    if bg.size < 100:
        return False
    edges = cv2.Canny(gray, 70, 180)
    bg_edges = edges[mask > 0]
    density = float(np.mean(bg_edges > 0))
    return density > 0.11


def validate_selfie_profile(
    image: np.ndarray,
    *,
    analyzer: FaceAnalyzer | None = None,
) -> SelfieProfileReport:
    """Hard gate for live selfies — document uploads skip this."""
    settings = get_settings()
    bgr = _to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    issues: list[str] = []
    checks: dict[str, bool] = {}

    if min(h, w) < 320:
        issues.append("low_quality")
        checks["resolution"] = False
    else:
        checks["resolution"] = True

    faces_analyzer = analyzer or get_face_analyzer()
    faces = faces_analyzer.detect(bgr, document_mode=False)

    if len(faces) == 0:
        issues.append("no_face")
        checks["single_face"] = False
    elif len(faces) > 1:
        issues.append("multiple_faces")
        checks["single_face"] = False
    else:
        checks["single_face"] = True

    if not faces:
        messages = [ISSUE_MESSAGES[i] for i in issues]
        return SelfieProfileReport(passed=False, score=0.0, issues=issues, messages=messages, checks=checks)

    face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
    x, y, bw, bh = face.bbox
    face_area = bw * bh
    img_area = max(w * h, 1)
    area_ratio = face_area / img_area
    min_area = getattr(settings, "selfie_min_face_area_ratio", 0.14)
    checks["face_size"] = area_ratio >= min_area
    if not checks["face_size"]:
        issues.append("face_too_small")

    cx, cy = x + bw / 2, y + bh / 2
    checks["face_centered"] = (0.22 * w <= cx <= 0.78 * w) and (0.18 * h <= cy <= 0.82 * h)
    if not checks["face_centered"]:
        issues.append("face_off_center")

    margin = 0.04
    checks["not_cropped"] = (
        x >= w * margin
        and y >= h * margin
        and (x + bw) <= w * (1 - margin)
        and (y + bh) <= h * (1 - margin)
    )
    if not checks["not_cropped"]:
        issues.append("face_cropped")

    face_bgr = _face_crop(bgr, face.bbox)
    face_gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    lap = float(cv2.Laplacian(face_gray, cv2.CV_64F).var())
    min_blur = getattr(settings, "selfie_min_blur_laplacian", 90.0)
    checks["sharpness"] = lap >= min_blur
    if not checks["sharpness"]:
        issues.append("too_blurry")

    brightness = float(np.mean(face_gray)) / 255.0
    checks["lighting"] = 0.28 <= brightness <= 0.88
    if brightness < 0.28:
        issues.append("too_dark")
    elif brightness > 0.88:
        issues.append("too_bright")

    glare = float(np.mean(face_gray > 245))
    checks["no_glare"] = glare <= 0.08
    if not checks["no_glare"]:
        issues.append("glare")

    checks["no_glasses"] = not _detect_glasses(face_gray)
    if not checks["no_glasses"]:
        issues.append("glasses_detected")

    checks["face_visible"] = not _detect_face_cover(face_gray)
    if not checks["face_visible"]:
        issues.append("face_covered")

    checks["plain_background"] = not _busy_background(bgr, face.bbox)
    if not checks["plain_background"]:
        issues.append("busy_background")

    insightface_pose = None
    if face.pose_yaw is not None and face.pose_pitch is not None and face.pose_roll is not None:
        insightface_pose = (face.pose_yaw, face.pose_pitch, face.pose_roll)

    pose_analyzer = get_openface_analyzer()
    pose_report = pose_analyzer.analyze(
        bgr,
        face.bbox,
        insightface_pose=insightface_pose,
        limits=pose_analyzer.selfie_limits,
    )
    checks["head_pose"] = pose_report.passed
    if not pose_report.passed:
        settings = get_settings()
        yaw = pose_report.head_pose_yaw
        pitch = pose_report.head_pose_pitch
        roll = pose_report.head_pose_roll
        if yaw is not None and abs(yaw) > settings.selfie_max_yaw:
            issues.append("head_turned")
        elif pitch is not None and pitch > settings.selfie_max_pitch:
            issues.append("head_tilted_up")
        elif pitch is not None and pitch < -settings.selfie_max_pitch:
            issues.append("head_tilted_down")
        elif roll is not None and abs(roll) > settings.selfie_max_roll:
            issues.append("head_rolled")
        else:
            issues.append("head_pose_invalid")

    passed = len(issues) == 0
    score_parts = [1.0 if v else 0.0 for v in checks.values()]
    score = float(sum(score_parts) / len(score_parts)) if score_parts else 0.0
    messages = [ISSUE_MESSAGES[i] for i in issues if i in ISSUE_MESSAGES]

    return SelfieProfileReport(
        passed=passed,
        score=score,
        issues=issues,
        messages=messages,
        checks=checks,
    )
