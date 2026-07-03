"""VIN + serial parsing. Pure functions — always available (no heavy deps)."""
from __future__ import annotations

import re

# ISO 3779: 17 chars, excludes I, O, Q.
_VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")
_SERIAL_RE = re.compile(r"\b[A-Z0-9]{6,20}\b")

_TRANSLIT = {
    **{str(d): d for d in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def is_valid_vin(vin: str) -> bool:
    """Validate length, charset, and the ISO-3779 check digit (position 9)."""
    vin = vin.strip().upper()
    if len(vin) != 17 or not _VIN_RE.fullmatch(vin):
        return False
    total = sum(_TRANSLIT.get(c, 0) * w for c, w in zip(vin, _WEIGHTS, strict=True))
    check = total % 11
    expected = "X" if check == 10 else str(check)
    return vin[8] == expected


def extract_vin_candidates(text: str) -> list[str]:
    """Return unique 17-char VIN-shaped tokens, valid ones first.

    We scan token-by-token (VINs are commonly printed with surrounding spaces or
    hyphens) rather than stripping all whitespace, which would glue adjacent text
    onto the VIN and break detection.
    """
    found: list[str] = []
    for token in re.split(r"[\s\-]+", text.upper()):
        for m in _VIN_RE.findall(token):
            if m not in found:
                found.append(m)
    return sorted(found, key=lambda v: not is_valid_vin(v))


def extract_serials(text: str, *, exclude: set[str] | None = None) -> list[str]:
    """Generic alphanumeric serials (component serial numbers)."""
    exclude = exclude or set()
    out = []
    for tok in _SERIAL_RE.findall(text.upper()):
        if tok in exclude or len(tok) == 17 and is_valid_vin(tok):
            continue
        if tok not in out:
            out.append(tok)
    return out
