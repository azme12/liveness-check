"""ML adapters for document OCR, liveness, and face matching."""

from liveness.ml.active_challenge import ChallengeResult, evaluate_challenge, needs_active_challenge
from liveness.ml.device_intel import DeviceFingerprint, build_fingerprint
from liveness.ml.document_authenticity import DocumentAuthenticityReport, assess_document_authenticity
from liveness.ml.face import FaceAnalyzer, FaceMatchReport
from liveness.ml.face_gallery import FaceGallery, GalleryEnrollResult, GalleryMatch
from liveness.ml.face_mesh import FaceMeshAnalyzer, FaceMeshReport, get_face_mesh_analyzer
from liveness.ml.fraud import FraudAssessment, compute_fraud_score
from liveness.ml.liveness import LivenessDetector, LivenessReport
from liveness.ml.openface import ActiveLivenessReport, OpenFaceAnalyzer, evaluate_head_pose, get_openface_analyzer
from liveness.ml.ocr import DocumentOcr, OcrReport
from liveness.ml.quality import QualityReport, assess_quality, decode_image
from liveness.ml.replay import ReplaySignals, analyze_replay_cues
from liveness.ml.selfie_profile import SelfieProfileReport, validate_selfie_profile

__all__ = [
    "assess_quality",
    "decode_image",
    "validate_selfie_profile",
    "SelfieProfileReport",
    "QualityReport",
    "LivenessDetector",
    "LivenessReport",
    "FaceAnalyzer",
    "FaceMatchReport",
    "FaceGallery",
    "GalleryEnrollResult",
    "GalleryMatch",
    "FaceMeshAnalyzer",
    "FaceMeshReport",
    "get_face_mesh_analyzer",
    "OpenFaceAnalyzer",
    "ActiveLivenessReport",
    "evaluate_head_pose",
    "DocumentOcr",
    "OcrReport",
    "compute_fraud_score",
    "FraudAssessment",
    "analyze_replay_cues",
    "ReplaySignals",
    "build_fingerprint",
    "DeviceFingerprint",
    "DocumentAuthenticityReport",
    "assess_document_authenticity",
    "ChallengeResult",
    "evaluate_challenge",
    "needs_active_challenge",
]
