"""Small, deterministic cleaning helpers used by every data source."""

from __future__ import annotations

import re
import unicodedata


def normalize_text(value: object) -> str:
    """Return comparable lowercase text without accents or extra punctuation."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def clean_isbn(value: object) -> str:
    """Keep only ISBN digits and the possible ISBN-10 X check digit."""
    return re.sub(r"[^0-9Xx]", "", "" if value is None else str(value)).upper()


def is_valid_isbn13(value: object) -> bool:
    isbn = clean_isbn(value)
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    expected = (10 - sum((1 if idx % 2 == 0 else 3) * int(char) for idx, char in enumerate(isbn[:12])) % 10) % 10
    return expected == int(isbn[-1])


def split_authors(value: object) -> list[str]:
    """Split the semicolon-delimited author convention used by demo sources."""
    return [part.strip() for part in str(value or "").split(";") if part.strip()]

