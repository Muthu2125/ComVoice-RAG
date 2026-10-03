import re
from decimal import Decimal, InvalidOperation


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return text.strip()


def quote_exists(quote: str, page_text: str) -> bool:
    if not quote or not page_text:
        return False
    return normalize_text(quote) in normalize_text(page_text)


NUMBER_PATTERN = re.compile(
    r"""
    (?:
        \$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|m|bn))?
        |
        \b\d{1,4}(?:[/-]\d{1,2}){1,2}\b
        |
        \b\d[\d,]*(?:\.\d+)?\s?%
        |
        \b\d[\d,]*(?:\.\d+)?\b
    )
    """,
    re.I | re.X,
)


def extract_numbers(text: str):
    return [normalize_text(x) for x in NUMBER_PATTERN.findall(text or "")]


def numbers_supported(claim: str, page_text: str) -> bool:
    nums = extract_numbers(claim)
    if not nums:
        return True
    page_norm = normalize_text(page_text)
    return all(n in page_norm for n in nums)
