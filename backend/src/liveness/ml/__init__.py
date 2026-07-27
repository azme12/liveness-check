"""ML adapters for document OCR, liveness, and face matching."""

from liveness.ml.face import FaceAnalyzer, FaceMatchReport
from liveness.ml.liveness import LivenessDetector, LivenessReport
from liveness.ml.ocr import DocumentOcr, OcrReport
from liveness.ml.quality import QualityReport, assess_quality, decode_image

__all__ = [
    "assess_quality",
    "decode_image",
    "QualityReport",
    "LivenessDetector",
    "LivenessReport",
    "FaceAnalyzer",
    "FaceMatchReport",
    "DocumentOcr",
    "OcrReport",
]
