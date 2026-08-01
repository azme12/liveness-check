"""Document OCR / MRZ extraction — PaddleOCR or Tesseract only."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from liveness.ml.document_types import detect_document_type_from_text
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
_PRODUCTION_OCR_BACKENDS = frozenset({"paddleocr", "tesseract"})


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
    mrz = [ln.replace(" ", "") for ln in lines if _MRZ_LINE.match(ln.replace(" ", ""))]
    if len(mrz) < 2:
        return None
    line = mrz[1]
    if len(line) != 44:
        return None

    values = {str(i): i for i in range(10)}
    values.update({chr(ord("A") + i): 10 + i for i in range(26)})
    values["<"] = 0
    weights = (7, 3, 1)

    def valid(data: str, digit: str) -> bool:
        if not digit.isdigit():
            return False
        total = sum(values.get(ch, 0) * weights[i % 3] for i, ch in enumerate(data))
        return total % 10 == int(digit)

    document_ok = valid(line[0:9], line[9])
    birth_ok = valid(line[13:19], line[19])
    expiry_ok = valid(line[21:27], line[27])
    optional_ok = valid(line[28:42], line[42])
    composite = line[0:10] + line[13:20] + line[21:43]
    composite_ok = valid(composite, line[43])
    return document_ok and birth_ok and expiry_ok and optional_ok and composite_ok


class DocumentOcr:
    def __init__(self) -> None:
        self._ocr = None
        self._backend = "unavailable"
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            self._backend = "paddleocr"
        except Exception:
            self._ocr = None
        if self._ocr is None:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self._backend = "tesseract"
            except Exception:
                self._backend = "unavailable"

    @property
    def production_ready(self) -> bool:
        return self._backend in _PRODUCTION_OCR_BACKENDS

    def extract(self, image: np.ndarray) -> OcrReport:
        if not self.production_ready:
            return OcrReport(
                fields=DocumentFields(),
                mrz_valid=None,
                document_type=None,
                backend="unavailable",
                warnings=["ocr_engine_required"],
            )

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
        elif self._backend == "tesseract":
            try:
                import cv2
                import pytesseract

                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
                general = pytesseract.image_to_string(gray, config="--psm 6")
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                mrz_text = pytesseract.image_to_string(
                    binary,
                    config="--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<",
                )
                texts.extend(line.strip().upper() for line in general.splitlines() if line.strip())
                texts.extend(line.strip().upper() for line in mrz_text.splitlines() if line.strip())
                texts = list(dict.fromkeys(texts))
            except Exception as exc:
                return OcrReport(
                    fields=DocumentFields(),
                    mrz_valid=None,
                    document_type=None,
                    backend=self._backend,
                    warnings=[f"ocr_error:{exc}"],
                )

        fields = _parse_td3(texts) or DocumentFields()
        if not fields.full_name and texts:
            candidates = [t for t in texts if " " in t and not _MRZ_LINE.match(t.replace(" ", ""))]
            if candidates:
                fields.full_name = candidates[0].title()

        return OcrReport(
            fields=fields,
            mrz_valid=_mrz_checksum_ok(texts),
            document_type=detect_document_type_from_text(texts),
            backend=self._backend,
            raw_text=texts[:50],
        )
