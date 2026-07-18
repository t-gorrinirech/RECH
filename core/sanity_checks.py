import math
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from core.personalities import Personality
from core.tokenizer import Token

MIN_FIELDS = 3
LOW_RANGE_MAX = 6
AVERAGE_LINE_BYTES = 20

PERSONALITY_REQUIRED_HINTS = {
    "sentimental": (
        [
            "family_and_relationships.pet_names",
            "family_and_relationships.mother_name",
            "family_and_relationships.father_name",
            "family_and_relationships.partner_name",
            "family_and_relationships.important_dates",
            "address_data.childhood_street",
        ],
        "sentimental relies on pet/family/affective-date fields",
    ),
    "fanatic": (
        [
            "interests_and_fandom.favorite_team",
            "interests_and_fandom.favorite_sport",
            "interests_and_fandom.favorite_celebrity",
            "interests_and_fandom.favorite_saga_or_character",
        ],
        "fanatic relies on team/sport/celebrity fields",
    ),
    "gamer": (
        ["personal_info.nickname"],
        "gamer relies on the nickname anchor token",
    ),
    "corporate": (
        ["work_and_career.job_role", "education.degree_studied"],
        "corporate relies on role/profession fields",
    ),
}

SUBSTITUTION_HEAVY = {"paranoid", "technical"}
SUBSTITUTION_LIGHT = {"lazy", "sentimental"}
UPPERCASE_FACTOR = 2.5
SLOW_FILL_RATIO = 0.2
LONG_MIN_LENGTH = 8
LONG_MIN_PENALTY = 2.0


@dataclass
class CheckResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.errors


def _origins(tokens: List[Token]) -> set:
    return {token.origin for token in tokens}


def _check_completeness(
    tokens: List[Token], personality: Personality, result: CheckResult
):
    origins = _origins(tokens)
    hint = PERSONALITY_REQUIRED_HINTS.get(personality.personality_id)
    if hint is not None:
        required, message = hint
        if not any(origin in origins for origin in required):
            result.warnings.append(
                f"[completeness] {message}; output will be low-variety"
            )
    if personality.priority_fields:
        filled = sum(
            1 for field_origin in personality.priority_fields if field_origin in origins
        )
        scope = "priority"
    else:
        filled = len(tokens)
        scope = "total"
    if filled < MIN_FIELDS:
        result.warnings.append(
            f"[completeness] only {filled} {scope} field(s) filled for '{personality.personality_id}' "
            f"(recommended >= {MIN_FIELDS})"
        )


def _check_flags(
    personality: Personality,
    special_chars_present: bool,
    length_range: Tuple[int, int],
    result: CheckResult,
):
    pid = personality.personality_id
    if special_chars_present and pid in SUBSTITUTION_LIGHT:
        result.warnings.append(
            "[flags] symbols will be inserted with low variety on this personality; expected human-mode limitation"
        )
    if not special_chars_present and pid in SUBSTITUTION_HEAVY:
        result.warnings.append(
            "[flags] consider -sc for higher realism on this personality"
        )
    minimum, maximum = length_range
    if minimum <= 0 or maximum <= 0 or minimum > maximum:
        result.errors.append(
            f"[flags] invalid --range {minimum},{maximum} (values must be > 0 and min <= max)"
        )
    elif maximum < LOW_RANGE_MAX:
        result.warnings.append(
            f"[flags] --range max {maximum} is very low; limited combinatorics"
        )


def _structural_space(tokens: List[Token], depth_max: int) -> int:
    token_count = len(tokens)
    if token_count == 0:
        return 0
    average_variants = sum(len(token.variants) for token in tokens) / token_count
    total = 0
    for depth in range(1, min(depth_max, token_count) + 1):
        permutations = math.perm(token_count, depth)
        total += int(permutations * (average_variants**depth))
    return total


def _mutation_multiplier(
    personality: Personality,
    special_chars_present: bool,
    forced_pool: List[str],
    uppercase: bool,
) -> float:
    multiplier = 1.0
    if uppercase:
        multiplier *= UPPERCASE_FACTOR
    if special_chars_present:
        pool_size = len(forced_pool) or 1
        appearance = max(personality.connector.probability_of_appearance, 0.5)
        multiplier *= 1.0 + appearance * pool_size
        leet = personality.letter_substitution_probability
        if leet:
            multiplier *= 1.0 + sum(float(value) for value in leet.values())
    return multiplier


def _check_feasibility(
    structural: int,
    multiplier: float,
    space: int,
    size: int,
    allow_relax: bool,
    result: CheckResult,
):
    if size <= space:
        return
    percentage = (space / size * 100) if size else 0.0
    detail = (
        f"~{structural} distinct data combinations from the filled fields"
        if multiplier <= 1.0
        else f"~{structural} data combinations, ~{space} incl. symbol/case/leet mutations"
    )
    if allow_relax:
        result.warnings.append(
            f"[feasibility] you asked for {size} passwords but only {detail} are reachable; "
            f"--allow-relax is on, so personality and symbol restrictions will be loosened "
            f"to get closer to the target"
        )
    else:
        result.warnings.append(
            f"[feasibility] you asked for {size} passwords but only {detail} are reachable "
            f"(~{percentage:.1f}% of your request); generation will stop early. "
            f"Fill more input fields, lower --size, or pass --allow-relax"
        )


def _check_runtime(
    space: int,
    size: int,
    length_range: Tuple[int, int],
    result: CheckResult,
):
    if space <= 0:
        return
    minimum, _ = length_range
    difficulty = size / space
    if minimum >= LONG_MIN_LENGTH:
        difficulty *= LONG_MIN_PENALTY
    if difficulty > SLOW_FILL_RATIO:
        result.warnings.append(
            "[runtime] this combination of options (personality, size, range and symbols) "
            "will likely take longer than usual to generate; "
            "lower --size, widen --range, or fill more input fields to speed it up"
        )


def _check_output(
    output_path: Optional[str], size: int, debug: bool, result: CheckResult
):
    if output_path is None:
        return
    path = Path(output_path)
    parent = path.parent if str(path.parent) else Path(".")
    if path.exists() and path.is_dir():
        result.errors.append(f"[output] {output_path} is a directory")
        return
    if not parent.exists():
        result.errors.append(f"[output] directory {parent} does not exist")
        return
    if not os.access(parent, os.W_OK):
        result.errors.append(f"[output] no write permission on {parent}")
        return
    needed = size * AVERAGE_LINE_BYTES
    free = shutil.disk_usage(parent).free
    if free < needed:
        result.errors.append(
            f"[output] not enough disk space: need ~{needed} bytes, have {free}"
        )
    if debug and size >= 1_000_000:
        result.warnings.append(
            "[output] --debug with large size produces metadata heavier than the wordlist itself"
        )


def run_checks(
    tokens: List[Token],
    personality: Personality,
    special_chars_present: bool,
    length_range: Tuple[int, int],
    size: int,
    depth_max: int,
    allow_relax: bool,
    output_path: Optional[str],
    debug: bool,
    forced_pool: Optional[List[str]] = None,
    uppercase: bool = False,
) -> CheckResult:
    result = CheckResult()
    _check_completeness(tokens, personality, result)
    _check_flags(personality, special_chars_present, length_range, result)
    structural = _structural_space(tokens, depth_max)
    multiplier = _mutation_multiplier(
        personality, special_chars_present, forced_pool or [], uppercase
    )
    space = int(structural * multiplier)
    _check_feasibility(structural, multiplier, space, size, allow_relax, result)
    _check_runtime(space, size, length_range, result)
    _check_output(output_path, size, debug, result)
    return result
