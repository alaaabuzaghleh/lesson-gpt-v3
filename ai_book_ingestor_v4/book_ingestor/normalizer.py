from __future__ import annotations
import re
import unicodedata

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_TATWEEL = "\u0640"

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_ARABIC_CHAR = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_ARABIC_WORD = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
_ARABIC_PHRASE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+(?:\s+[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)*"
)
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_HTML_TAG = re.compile(r"(<[^>]+>)")

# Textbook vocabulary used to tell logical Arabic from PaddleOCR visual order.
# Teh marbuta never begins a logical word, so a leading ة is also a visual signal.
_LOGICAL_ARABIC_WORDS = frozenset(
    {
        "وزارة",
        "التعليم",
        "تعليم",
        "الرياضيات",
        "رياضيات",
        "المملكة",
        "العربية",
        "السعودية",
        "الفصل",
        "الوحدة",
        "الدرس",
        "كتاب",
        "الطالب",
        "المعلم",
        "المسارات",
        "مسارات",
        "مقرر",
        "نظام",
        "المدرسة",
        "الصف",
        "تمرين",
        "التمرين",
        "مثال",
        "الحل",
        "قانون",
        "القانون",
        "القوة",
        "الكتلة",
        "الطاقة",
        "الحركة",
        "الدالة",
        "معادلة",
        "المعادلة",
        "المثلث",
        "الدائرة",
        "الجزء",
        "الثاني",
        "الأول",
        "الأولى",
        "الاولى",
        "الثانية",
        "مقدمة",
        "المقدمة",
        "نشاط",
        "النشاط",
        "مسألة",
        "المسألة",
        "تطبيق",
        "التطبيق",
        "مفهوم",
        "المفهوم",
        "تعريف",
        "التعريف",
        "نظرية",
        "النظرية",
        "العلوم",
        "الفيزياء",
        "الكيمياء",
        "الأحياء",
        "الاحياء",
        "اللغة",
        "الإنجليزية",
        "الانجليزية",
        "التاريخ",
        "الجغرافيا",
        "الدراسية",
        "الدراسي",
        "الوطني",
        "الطلاب",
        "المعلمين",
    }
)
_VISUAL_ARABIC_WORDS = frozenset(word[::-1] for word in _LOGICAL_ARABIC_WORDS)
_LOGICAL_PREFIXES = ("ال", "وال", "بال", "فال", "كال", "لل")


def _arabic_word_visual_bias(word: str) -> int:
    """Positive scores mean the token looks like LTR-reversed visual Arabic."""
    if len(word) < 3:
        return 0
    score = 0
    if word in _VISUAL_ARABIC_WORDS:
        score += 2
    if word.startswith("ة"):
        score += 2
    if word in _LOGICAL_ARABIC_WORDS:
        score -= 2
    if any(word.startswith(prefix) and len(word) > len(prefix) for prefix in _LOGICAL_PREFIXES):
        score -= 2
    return score


def looks_like_visual_arabic(text: str) -> bool:
    """True when Arabic appears stored as left-to-right visual glyphs, e.g. ميلعتلا ةرازو."""
    words = [word for word in _ARABIC_WORD.findall(text) if len(word) >= 3]
    if not words:
        return False
    return sum(_arabic_word_visual_bias(word) for word in words) > 0


def restore_arabic_logical_order(text: str, *, force: bool | None = None) -> str:
    """Convert MinerU/PaddleOCR visual Arabic into logical right-to-left text.

    OCR often emits وزارة التعليم as ميلعتلا ةرازو (characters in on-page LTR order).
    Already-logical Arabic is left unchanged. When ``force`` is None, visual
    order is detected from the whole string so later lines on the same page
    are reversed even if they do not contain known vocabulary.
    """
    if not text or not _ARABIC_CHAR.search(text):
        return text
    if force is None:
        force = looks_like_visual_arabic(text)
    if "<" in text and ">" in text:
        parts = _HTML_TAG.split(text)
        if len(parts) > 1:
            return "".join(
                part if part.startswith("<") else restore_arabic_logical_order(part, force=force)
                for part in parts
            )
    if "\n" in text:
        return "\n".join(restore_arabic_logical_order(line, force=force) for line in text.split("\n"))
    if not force and not looks_like_visual_arabic(text):
        return text
    if not _LATIN_LETTER.search(text):
        return text[::-1]
    return _ARABIC_PHRASE.sub(lambda match: match.group(0)[::-1], text)


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
