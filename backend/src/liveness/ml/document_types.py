"""Supported ID document types for verification (Ethiopia + international)."""

from __future__ import annotations

SUPPORTED_DOCUMENT_TYPES = frozenset(
    {
        "passport",
        "fayda",
        "kebele_id",
        "national_id",
        "driving_license",
        "id_card",
    }
)

_ALIASES = {
    "fayda_id": "fayda",
    "fayda-id": "fayda",
    "digital_id": "fayda",
    "kebele": "kebele_id",
    "kebele-id": "kebele_id",
    "nationalid": "national_id",
    "national-id": "national_id",
    "ethiopian_id": "national_id",
    "drivers_license": "driving_license",
}


def normalize_document_type(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower().replace(" ", "_")
    if key in SUPPORTED_DOCUMENT_TYPES:
        return key
    return _ALIASES.get(key)


def detect_document_type_from_text(texts: list[str]) -> str | None:
    joined = " ".join(texts).upper()
    if any(k in joined for k in ("FAYDA", "FIN ", "DIGITAL ID", "FAYDA ID")):
        return "fayda"
    if any(k in joined for k in ("KEBELE", "WOREDA", "HOUSEHOLD")):
        return "kebele_id"
    if "PASSPORT" in joined or any(len(t.replace(" ", "")) == 44 for t in texts):
        return "passport"
    if any(k in joined for k in ("DRIVER", "LICEN", "DRIVING")):
        return "driving_license"
    if any(k in joined for k in ("ETHIOPIA", "FEDERAL", "IDENTITY", "ID CARD", "NATIONAL")):
        return "national_id"
    if texts:
        return "id_card"
    return None


def resolve_document_type(*, hint: str | None, ocr_detected: str | None) -> str | None:
    normalized_hint = normalize_document_type(hint)
    if normalized_hint:
        return normalized_hint
    return normalize_document_type(ocr_detected) or ocr_detected
