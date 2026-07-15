import random
from typing import List

from core.personalities import Personality

LETTER_SUBSTITUTIONS = {
    "a_to_at": ("a", "@"),
    "i_l_to_exclamation": ("il", "!"),
    "s_to_dollar": ("s", "$"),
    "e_to_asterisk": ("e", "*"),
    "o_to_zero": ("o", "0"),
}


def apply_letter_substitution(text: str, personality: Personality, rng: random.Random,
                              forced_present: bool) -> str:
    if not forced_present:
        return text
    probabilities = personality.letter_substitution_probability
    if not probabilities:
        return text
    char_probability = {}
    for key, (letters, symbol) in LETTER_SUBSTITUTIONS.items():
        probability = float(probabilities.get(key, 0.0))
        if probability <= 0.0:
            continue
        for letter in letters:
            char_probability[letter] = (probability, symbol)
    if not char_probability:
        return text
    result = []
    for char in text:
        entry = char_probability.get(char.lower())
        if entry is not None and rng.random() < entry[0]:
            result.append(entry[1])
        else:
            result.append(char)
    return "".join(result)


def pick_symbol(personality: Personality, forced_pool: List[str], rng: random.Random):
    connector = personality.connector
    if forced_pool:
        symbol = rng.choice(forced_pool)
    elif connector.forced_only:
        return None
    else:
        pool = personality.symbol_pool()
        if not pool:
            return None
        symbol = rng.choices(pool, weights=personality.symbol_weights(), k=1)[0]
    if rng.random() < connector.probability_of_duplicate:
        return symbol + symbol
    return symbol


def should_apply_symbol(personality: Personality, forced_present: bool, rng: random.Random) -> bool:
    if not forced_present:
        return False
    connector = personality.connector
    if connector.forced_only:
        return True
    probability = max(connector.probability_of_appearance, 0.5)
    return rng.random() < probability
