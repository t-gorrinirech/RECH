import random
from typing import Dict, Iterator, List

from core.leet import apply_letter_substitution, pick_symbol, should_apply_symbol
from core.personalities import Personality
from core.tokenizer import Token

SUFFIX_POSITIONS = {"suffix_end", "suffix_end_fixed_single"}
CONNECTOR_POSITIONS = {"connector_between_tokens"}
DEFAULT_DEPTH_WEIGHTS = {1: 0.2, 2: 0.5, 3: 0.3}
UPPERCASE_LEADING_WEIGHTS = {0: 0.2, 1: 0.5, 2: 0.22, 3: 0.08}


def _capitalize_leading(part: str, rng: random.Random) -> str:
    lowered = part.lower()
    counts = list(UPPERCASE_LEADING_WEIGHTS)
    probabilities = [UPPERCASE_LEADING_WEIGHTS[count] for count in counts]
    count = rng.choices(counts, weights=probabilities, k=1)[0]
    if count == 0:
        return lowered
    return lowered[:count].upper() + lowered[count:]


def _apply_case(parts: List[str], uppercase: bool, rng: random.Random) -> List[str]:
    if not uppercase:
        return [part.lower() for part in parts]
    return [_capitalize_leading(part, rng) for part in parts]


def select_mode(personality: Personality, rng: random.Random) -> str:
    base = personality.primary_mode
    other = "paranoid" if base == "human" else "human"
    if rng.random() < personality.mode_leak_probability:
        return other
    return base


def _split_point(text: str, rng: random.Random) -> int:
    if len(text) <= 1:
        return len(text)
    return rng.randint(1, len(text) - 1)


def _assemble_human(parts: List[str], personality: Personality, forced_pool: List[str],
                    forced_present: bool, rng: random.Random) -> str:
    connector = personality.connector
    apply_symbol = should_apply_symbol(personality, forced_present, rng)
    symbol = pick_symbol(personality, forced_pool, rng) if apply_symbol else None
    if symbol and connector.position in CONNECTOR_POSITIONS:
        body = symbol.join(parts)
    else:
        body = "".join(parts)
        if symbol and connector.position in SUFFIX_POSITIONS:
            body = body + symbol
    return apply_letter_substitution(body, personality, rng, forced_present)


def _assemble_paranoid(parts: List[str], personality: Personality, forced_pool: List[str],
                       forced_present: bool, rng: random.Random) -> str:
    combined = parts[0]
    for extra in parts[1:]:
        split = _split_point(combined, rng)
        symbol = ""
        if should_apply_symbol(personality, forced_present, rng):
            picked = pick_symbol(personality, forced_pool, rng)
            symbol = picked or ""
        combined = combined[:split] + symbol + extra + combined[split:]
    if should_apply_symbol(personality, forced_present, rng):
        trailing = pick_symbol(personality, forced_pool, rng)
        if trailing:
            combined = combined + trailing
    return apply_letter_substitution(combined, personality, rng, forced_present)


def _weighted_sample(tokens: List[Token], weights: List[float], count: int,
                     rng: random.Random) -> List[Token]:
    pool = list(range(len(tokens)))
    pool_weights = list(weights)
    chosen = []
    for _ in range(min(count, len(pool))):
        index = rng.choices(range(len(pool)), weights=pool_weights, k=1)[0]
        chosen.append(tokens[pool[index]])
        pool.pop(index)
        pool_weights.pop(index)
    return chosen


def stream_candidates(tokens: List[Token], personality: Personality, forced_pool: List[str],
                      forced_present: bool, rng: random.Random, depth_max: int = 3,
                      depth_weights: Dict[int, float] = None, uppercase: bool = False) -> Iterator[dict]:
    if not tokens:
        return
    depth_weights = depth_weights or DEFAULT_DEPTH_WEIGHTS
    weights = personality.compute_weights(tokens)
    depths = [depth for depth in depth_weights if depth <= depth_max]
    depth_probabilities = [depth_weights[depth] for depth in depths]
    while True:
        depth = rng.choices(depths, weights=depth_probabilities, k=1)[0]
        selected = _weighted_sample(tokens, weights, depth, rng)
        parts = _apply_case([rng.choice(token.variants) for token in selected], uppercase, rng)
        mode = select_mode(personality, rng)
        if mode == "paranoid":
            password = _assemble_paranoid(parts, personality, forced_pool, forced_present, rng)
        else:
            password = _assemble_human(parts, personality, forced_pool, forced_present, rng)
        yield {
            "password": password,
            "personality": personality.personality_id,
            "mode": mode,
            "tokens": [token.origin for token in selected],
            "parts": parts,
        }
