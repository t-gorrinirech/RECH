import random

from core.assembler import stream_candidates
from core.personalities import load_personality
from core.tokenizer import tokenize

SAMPLE_SIZE = 4000
SEED = 42


DEFAULT_POOL = ["_", ".", "-", "!", "@", "*", "$", "?", "&", "%"]


def _sample(personality_id, sample_input, field_types, forced_pool=None, forced_present=False,
            uppercase=False):
    tokens = tokenize(sample_input, field_types, allow_symbols=forced_present)
    profile = load_personality(personality_id)
    rng = random.Random(SEED)
    stream = stream_candidates(tokens, profile, forced_pool or [], forced_present, rng,
                               depth_max=3, uppercase=uppercase)
    passwords = []
    modes = []
    for _ in range(SAMPLE_SIZE):
        candidate = next(stream)
        passwords.append(candidate["password"])
        modes.append(candidate["mode"])
    return passwords, modes


def _symbol_ratio(passwords):
    with_symbol = sum(1 for pw in passwords if any(not c.isalnum() for c in pw))
    return with_symbol / len(passwords)


def _avg_length(passwords):
    return sum(len(pw) for pw in passwords) / len(passwords)


def _avg_symbols(passwords):
    return sum(sum(1 for c in pw if not c.isalnum()) for pw in passwords) / len(passwords)


def test_paranoid_has_more_symbols_than_sentimental(sample_input, field_types):
    paranoid, _ = _sample("paranoid", sample_input, field_types,
                          forced_pool=DEFAULT_POOL, forced_present=True)
    sentimental, _ = _sample("sentimental", sample_input, field_types,
                             forced_pool=DEFAULT_POOL, forced_present=True)
    assert _symbol_ratio(paranoid) > _symbol_ratio(sentimental)


def test_no_symbols_without_special_chars(sample_input, field_types):
    for pid in ("paranoid", "gamer", "technical", "corporate", "fanatic", "sentimental", "default"):
        passwords, _ = _sample(pid, sample_input, field_types)
        assert _symbol_ratio(passwords) == 0.0


def test_no_uppercase_without_flag(sample_input, field_types):
    for pid in ("paranoid", "gamer", "corporate", "sentimental", "default"):
        passwords, _ = _sample(pid, sample_input, field_types)
        assert all(pw == pw.lower() for pw in passwords)


def test_uppercase_flag_produces_uppercase(sample_input, field_types):
    passwords, _ = _sample("default", sample_input, field_types, uppercase=True)
    with_upper = sum(1 for pw in passwords if any(c.isupper() for c in pw))
    assert with_upper > 0
    assert any(pw != pw.lower() for pw in passwords)


def test_lazy_symbol_ratio_is_low(sample_input, field_types):
    lazy, _ = _sample("lazy", sample_input, field_types)
    assert _symbol_ratio(lazy) < 0.15


def test_paranoid_mode_dominates_for_paranoid_personality(sample_input, field_types):
    _, modes = _sample("paranoid", sample_input, field_types)
    paranoid_share = modes.count("paranoid") / len(modes)
    assert paranoid_share > 0.8


def test_human_mode_dominates_for_lazy_personality(sample_input, field_types):
    _, modes = _sample("lazy", sample_input, field_types)
    human_share = modes.count("human") / len(modes)
    assert human_share > 0.9


def test_personalities_produce_distinct_symbol_distributions(sample_input, field_types):
    densities = {}
    for pid in ("lazy", "sentimental", "technical", "paranoid", "corporate", "gamer"):
        passwords, _ = _sample(pid, sample_input, field_types,
                               forced_pool=DEFAULT_POOL, forced_present=True)
        densities[pid] = round(_avg_symbols(passwords), 2)
    assert len(set(densities.values())) >= 4
    assert densities["paranoid"] == max(densities.values())
    assert densities["paranoid"] > densities["corporate"]


def test_forced_symbols_activate_lazy(sample_input, field_types):
    baseline, _ = _sample("lazy", sample_input, field_types)
    forced, _ = _sample("lazy", sample_input, field_types,
                         forced_pool=["!", "@", "$"], forced_present=True)
    assert _symbol_ratio(forced) > _symbol_ratio(baseline)


def test_generation_is_reproducible(sample_input, field_types):
    first, _ = _sample("gamer", sample_input, field_types)
    second, _ = _sample("gamer", sample_input, field_types)
    assert first == second
