import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

EMPTY_MARKER = "WRITE HERE"
DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%Y-%m-%d", "%Y/%m/%d"]

FULL = "full"
LIGHT = "light"
NONE = "none"
TIER_LEVELS = {"core": FULL, "close": LIGHT, "distant": NONE}


@dataclass
class Token:
    origin: str
    field_type: str
    base: str
    variants: List[str]
    tier: str


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


def _name_chunks(word: str, level: str) -> List[str]:
    if len(word) < 4:
        return []
    chunks = []
    if level in (FULL, LIGHT):
        chunks.append(word[:4])
        chunks.append(word[-3:])
    if level == FULL:
        chunks.append(word[:3])
        chunks.append(word[-4:])
        chunks.append(word.rstrip("aeiou"))
    return chunks


def _proper_name_variants(value: str, level: str) -> List[str]:
    lower = value.lower()
    words = _words(lower)
    variants = [value, lower, value.capitalize(), value.upper()]
    if len(words) > 1:
        variants.append("".join(words))
        if level in (FULL, LIGHT):
            variants.extend(words)
    targets = words if len(words) > 1 else [lower]
    for word in targets:
        variants.extend(_name_chunks(word, level))
    return _dedup(variants)


def _username_variants(value: str, level: str) -> List[str]:
    stripped = value.replace("_", "").replace(".", "")
    variants = [value, value.lower(), stripped, stripped.lower(), value.capitalize()]
    return _dedup(variants)


def _place_variants(value: str, level: str) -> List[str]:
    words = _words(value)
    variants = [value, value.lower(), "".join(words).lower(), value.capitalize()]
    if words:
        if level in (FULL, LIGHT):
            variants.append(words[0].lower())
        if level == FULL and len(words) > 1:
            acronym = "".join(word[0] for word in words)
            variants.append(acronym.lower())
            variants.append(acronym.upper())
    return _dedup(variants)


def _free_text_variants(value: str, level: str) -> List[str]:
    words = _words(value)
    variants = [value.lower(), "".join(words).lower()]
    if level in (FULL, LIGHT):
        variants.extend(word.lower() for word in words)
        if len(words) > 1:
            variants.append(words[0].lower())
    if level == FULL and len(words) > 1:
        variants.append("".join(word[0] for word in words).lower())
    return _dedup(variants)


def _structured_number_variants(value: str, level: str) -> List[str]:
    digits = re.sub(r"\D", "", value)
    variants = [value]
    if digits:
        variants.append(digits)
        tails = {FULL: (2, 3, 4), LIGHT: (2,), NONE: ()}[level]
        for tail in tails:
            if len(digits) > tail:
                variants.append(digits[-tail:])
    return _dedup(variants)


def _short_number_variants(value: str, level: str) -> List[str]:
    return _dedup([value, re.sub(r"\D", "", value)])


def _parse_date(value: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _date_variants(value: str, level: str) -> List[str]:
    parsed = _parse_date(value)
    if parsed is not None:
        day = f"{parsed.day:02d}"
        month = f"{parsed.month:02d}"
        year = f"{parsed.year:04d}"
        short_year = year[-2:]
        variants = [f"{day}{month}{year}"]
        if level in (FULL, LIGHT):
            variants.extend([f"{day}{month}{short_year}", year, short_year])
        if level == FULL:
            variants.extend([
                f"{day}{month}",
                f"{month}{day}",
                f"{year}{month}{day}",
                str(parsed.day),
                str(parsed.month),
            ])
        return _dedup(variants)
    digits = re.sub(r"\D", "", value)
    if digits:
        variants = [digits]
        if len(digits) <= 2:
            variants.append(digits.zfill(2))
        tails = {FULL: (2, 3), LIGHT: (2,), NONE: ()}[level]
        for tail in tails:
            if len(digits) > tail:
                variants.append(digits[-tail:])
        return _dedup(variants)
    return _free_text_variants(value, level)


_VARIANT_BUILDERS = {
    "proper_name": _proper_name_variants,
    "username_handle": _username_variants,
    "place_name": _place_variants,
    "free_text": _free_text_variants,
    "structured_number": _structured_number_variants,
    "short_number": _short_number_variants,
    "date": _date_variants,
}


def _resolve_level(origin: str, tier: str, priority_fields: set) -> str:
    if origin in priority_fields:
        return FULL
    return TIER_LEVELS.get(tier, FULL)


def _build_token(origin: str, field_type: str, value: str, tier: str, level: str,
                 allow_spaces: bool, allow_symbols: bool) -> Token:
    builder = _VARIANT_BUILDERS.get(field_type, _free_text_variants)
    variants = builder(value, level)
    if not variants:
        variants = _dedup([value])
    if not allow_symbols:
        variants = _strip_symbols(variants)
    if not allow_spaces:
        variants = _strip_spaces(variants)
    if not variants:
        variants = _dedup([re.sub(r"\W", "", value)])
    return Token(origin=origin, field_type=field_type, base=value.strip(),
                 variants=variants, tier=tier)


def tokenize(input_data: Dict, field_types: Dict, allow_spaces: bool = False,
             allow_symbols: bool = True, field_tiers: Optional[Dict] = None,
             priority_fields: Optional[List[str]] = None) -> List[Token]:
    field_tiers = field_tiers or {}
    priority = set(priority_fields or [])
    tokens: List[Token] = []
    for category, fields in input_data.items():
        type_category = field_types.get(category, {})
        tier_category = field_tiers.get(category, {})
        if not isinstance(fields, dict):
            continue
        for field_name, value in fields.items():
            origin = f"{category}.{field_name}"
            field_type = type_category.get(field_name, "free_text")
            tier = tier_category.get(field_name, "core" if not field_tiers else "close")
            level = _resolve_level(origin, tier, priority)
            if isinstance(value, list):
                for element in value:
                    if not _is_empty(element):
                        tokens.append(_build_token(origin, field_type, str(element), tier,
                                                   level, allow_spaces, allow_symbols))
            elif not _is_empty(value):
                tokens.append(_build_token(origin, field_type, str(value), tier, level,
                                           allow_spaces, allow_symbols))
    return tokens
