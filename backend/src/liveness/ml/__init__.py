"""ML adapters for document OCR, liveness, and face matching."""

from liveness.ml.face import FaceAnalyzer, FaceMatchReport
from liveness.ml.face_gallery import FaceGallery, GalleryEnrollResult, GalleryMatch
from liveness.ml.liveness import LivenessDetector, LivenessReport
from liveness.ml.openface import ActiveLivenessReport, OpenFaceAnalyzer
from liveness.ml.ocr import DocumentOcr, OcrReport
from liveness.ml.quality import QualityReport, assess_quality, decode_image
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
    "OpenFaceAnalyzer",
    "ActiveLivenessReport",
    "DocumentOcr",
    "OcrReport",
]
