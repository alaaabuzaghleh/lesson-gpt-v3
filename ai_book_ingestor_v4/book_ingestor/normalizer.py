from __future__ import annotations
import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_arabic(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(ARABIC_DIGITS)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = re.sub(r"[إأآٱ]", "ا", text)
    text = text.replace("ى", "ي")
    # Keep ة and ه distinct; merging them hurts precision.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_general(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).translate(ARABIC_DIGITS)
    text = _ARABIC_DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = re.sub(r"[إأآٱ]", "ا", text).replace("ى", "ي")
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_search_text(*parts: object) -> str:
    flattened: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple, set)):
            flattened.extend(str(x) for x in part if x)
        else:
            flattened.append(str(part))
    return normalize_general(" | ".join(flattened))
