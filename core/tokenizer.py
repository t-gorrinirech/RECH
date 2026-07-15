import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

EMPTY_MARKER = "WRITE HERE"
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"]


@dataclass
class Token:
    origin: str
    field_type: str
    base: str
    variants: List[str]


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned == "" or cleaned.upper() == EMPTY_MARKER
    return False


def _strip_spaces(variants: List[str]) -> List[str]:
    return _dedup([variant.replace(" ", "") for variant in variants])


def _strip_symbols(variants: List[str]) -> List[str]:
    return _dedup([
        "".join(char for char in variant if char.isalnum() or char.isspace())
        for variant in variants
    ])


def _dedup(values: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            ordered.append(cleaned)
    return ordered


def _words(value: str) -> List[str]:
    return [word for word in re.split(r"[\s_.\-]+", value) if word]


def _proper_name_variants(value: str) -> List[str]:
    lower = value.lower()
    variants = [value, lower, value.capitalize(), value.upper()]
    if len(lower) >= 4:
        variants.append(lower[:3])
        variants.append(lower[:4])
        variants.append(lower.rstrip("aeiou"))
    return _dedup(variants)


def _username_variants(value: str) -> List[str]:
    stripped = value.replace("_", "").replace(".", "")
    variants = [value, value.lower(), stripped, stripped.lower(), value.capitalize()]
    return _dedup(variants)


def _place_variants(value: str) -> List[str]:
    words = _words(value)
    variants = [value, value.lower(), "".join(words).lower(), value.capitalize()]
    if len(words) > 1:
        acronym = "".join(word[0] for word in words)
        variants.append(acronym.lower())
        variants.append(acronym.upper())
    if words:
        variants.append(words[0].lower())
    return _dedup(variants)


def _free_text_variants(value: str) -> List[str]:
    words = _words(value)
    variants = [value.lower(), "".join(words).lower()]
    variants.extend(word.lower() for word in words)
    if len(words) > 1:
        variants.append("".join(word[0] for word in words).lower())
        variants.append(words[0].lower())
    return _dedup(variants)


def _structured_number_variants(value: str) -> List[str]:
    digits = re.sub(r"\D", "", value)
    variants = [value]
    if digits:
        variants.append(digits)
        for tail in (2, 3, 4):
            if len(digits) > tail:
                variants.append(digits[-tail:])
    return _dedup(variants)


def _short_number_variants(value: str) -> List[str]:
    return _dedup([value, re.sub(r"\D", "", value)])


def _parse_date(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _date_variants(value: str) -> List[str]:
    parsed = _parse_date(value)
    if parsed is not None:
        day = f"{parsed.day:02d}"
        month = f"{parsed.month:02d}"
        year = f"{parsed.year:04d}"
        short_year = year[-2:]
        return _dedup([
            f"{day}{month}{year}",
            f"{day}{month}{short_year}",
            f"{day}{month}",
            f"{month}{day}",
            f"{year}{month}{day}",
            year,
            short_year,
            str(parsed.day),
            str(parsed.month),
        ])
    digits = re.sub(r"\D", "", value)
    if digits:
        variants = [digits]
        if len(digits) <= 2:
            variants.append(digits.zfill(2))
        if len(digits) == 4:
            variants.append(digits[-2:])
        return _dedup(variants)
    return _free_text_variants(value)


_VARIANT_BUILDERS = {
    "proper_name": _proper_name_variants,
    "username_handle": _username_variants,
    "place_name": _place_variants,
    "free_text": _free_text_variants,
    "structured_number": _structured_number_variants,
    "short_number": _short_number_variants,
    "date": _date_variants,
}


def _build_token(origin: str, field_type: str, value: str, allow_spaces: bool,
                 allow_symbols: bool) -> Token:
    builder = _VARIANT_BUILDERS.get(field_type, _free_text_variants)
    variants = builder(value)
    if not variants:
        variants = _dedup([value])
    if not allow_symbols:
        variants = _strip_symbols(variants)
    if not allow_spaces:
        variants = _strip_spaces(variants)
    if not variants:
        variants = _dedup([re.sub(r"\W", "", value)])
    return Token(origin=origin, field_type=field_type, base=value.strip(), variants=variants)


def tokenize(input_data: Dict, field_types: Dict, allow_spaces: bool = False,
             allow_symbols: bool = True) -> List[Token]:
    tokens: List[Token] = []
    for category, fields in input_data.items():
        type_category = field_types.get(category, {})
        if not isinstance(fields, dict):
            continue
        for field_name, value in fields.items():
            origin = f"{category}.{field_name}"
            field_type = type_category.get(field_name, "free_text")
            if isinstance(value, list):
                for element in value:
                    if not _is_empty(element):
                        tokens.append(_build_token(origin, field_type, str(element), allow_spaces, allow_symbols))
            elif not _is_empty(value):
                tokens.append(_build_token(origin, field_type, str(value), allow_spaces, allow_symbols))
    return tokens
