"""Document OCR / MRZ extraction with optional PaddleOCR."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from liveness.types import DocumentFields, StructuredDate


@dataclass
class OcrReport:
    fields: DocumentFields
    mrz_valid: bool | None
    document_type: str | None
    backend: str
    raw_text: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_MRZ_LINE = re.compile(r"^[A-Z0-9<]{30,44}$")


def _parse_date_yymmdd(s: str) -> StructuredDate | None:
    if len(s) != 6 or not s.isdigit():
        return None
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    year = 1900 + yy if yy > 50 else 2000 + yy
    try:
        return StructuredDate(day=dd, month=mm, year=year)
    except Exception:
        return None


def _parse_td3(lines: list[str]) -> DocumentFields | None:
    """Parse ICAO TD3 (passport) MRZ when two lines of length 44 are present."""
    mrz = [ln.replace(" ", "") for ln in lines if _MRZ_LINE.match(ln.replace(" ", ""))]
    if len(mrz) < 2:
        return None
    l1, l2 = mrz[0], mrz[1]
    if len(l1) < 44 or len(l2) < 44:
        return None
    names = l1[5:44].split("<<")
    surname = names[0].replace("<", " ").strip()
    given = names[1].replace("<", " ").strip() if len(names) > 1 else ""
    full_name = f"{given} {surname}".strip()
    return DocumentFields(
        full_name=full_name or None,
        document_number=l2[0:9].replace("<", ""),
        nationality=l2[10:13].replace("<", ""),
        date_of_birth=_parse_date_yymmdd(l2[13:19]),
        sex=l2[20] if l2[20] in "MFX" else None,
        expiry_date=_parse_date_yymmdd(l2[21:27]),
        issuing_country=l1[2:5].replace("<", ""),
    )


def _mrz_checksum_ok(lines: list[str]) -> bool | None:
    """Basic presence check; full ICAO digit weights can be expanded later."""
    mrz = [ln.replace(" ", "") for ln in lines if _MRZ_LINE.match(ln.replace(" ", ""))]
    if len(mrz) < 2:
        return None
    return all(len(ln) in (30, 36, 44) for ln in mrz[:2])


class DocumentOcr:
    def __init__(self) -> None:
        self._ocr = None
        self._backend = "regex_fallback"
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            self._backend = "paddleocr"
        except Exception:
            self._ocr = None

    def extract(self, image: np.ndarray) -> OcrReport:
        texts: list[str] = []
        if self._ocr is not None:
            try:
                result = self._ocr.ocr(image, cls=True)
                if result and result[0]:
                    for line in result[0]:
                        texts.append(str(line[1][0]).upper())
            except Exception as exc:
                return OcrReport(
                    fields=DocumentFields(),
                    mrz_valid=None,
                    document_type=None,
                    backend=self._backend,
                    warnings=[f"ocr_error:{exc}"],
                )
        else:
            # No OCR engine — leave empty fields (API still runs quality + biometrics)
            pass

        fields = _parse_td3(texts) or DocumentFields()
        # Heuristic name from non-MRZ lines
        if not fields.full_name and texts:
            candidates = [t for t in texts if " " in t and not _MRZ_LINE.match(t.replace(" ", ""))]
            if candidates:
                fields.full_name = candidates[0].title()

        doc_type = None
        joined = " ".join(texts)
        if "PASSPORT" in joined or any(len(t.replace(" ", "")) == 44 for t in texts):
            doc_type = "passport"
        elif "DRIVER" in joined or "LICEN" in joined:
            doc_type = "driving_license"
        elif texts:
            doc_type = "id_card"

        return OcrReport(
            fields=fields,
            mrz_valid=_mrz_checksum_ok(texts),
            document_type=doc_type,
            backend=self._backend,
            raw_text=texts[:50],
        )
