"""
Lightweight language CONFIRMATION (not translation, not detection-before-OCR).

Context: OCR needs to know which language model to use BEFORE it can read
a document, so we still rely on the user's manual language selection to
run OCR (see documents.py). What this module does is check the OCR
OUTPUT text afterward, and flag if it looks like the wrong language was
selected - e.g. the user picked English, but the resulting text is mostly
Arabic script.

This works by counting which Unicode character ranges the letters in the
text actually belong to - no ML model or extra dependency needed, since
our two supported languages (English, Arabic) use visually distinct
alphabets. Good enough for "does this look right?" - not a general
purpose language identifier.
"""
import re

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_LATIN_RE = re.compile(r"[A-Za-z]")
# Letters that exist in Urdu but not in Arabic (ٹ ڈ ڑ ں ے ہ). If a page in
# Arabic script uses any of them it is (almost certainly) Urdu.
_URDU_ONLY_RE = re.compile(r"[ٹڈڑںےہ]")


def detect_script_language(text: str) -> str | None:
    """
    Returns "ur", "ar", "en", or None (not enough alphabetic text to judge -
    e.g. a document that's mostly numbers/tables).
    """
    if not text:
        return None

    arabic_count = len(_ARABIC_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    total = arabic_count + latin_count

    if total < 10:  # too little alphabetic text to judge confidently
        return None

    if arabic_count > latin_count:
        return "ur" if _URDU_ONLY_RE.search(text) else "ar"
    return "en"


if __name__ == "__main__":
    # Quick manual test.
    print(detect_script_language("INVOICE No. INV-0001 Client Name: Muhammad Qasim"))  # expect en
    print(detect_script_language("فاتورة رقم ١٢٣ اسم العميل"))  # expect ar
    print(detect_script_language("123 456 789"))  # expect None