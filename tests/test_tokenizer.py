from core.tokenizer import tokenize


def _origins(tokens):
    return {token.origin for token in tokens}


def test_write_here_is_excluded(field_types):
    data = {"personal_info": {"name": "WRITE HERE", "nickname": "Charly"}}
    tokens = tokenize(data, field_types)
    origins = _origins(tokens)
    assert "personal_info.nickname" in origins
    assert "personal_info.name" not in origins


def test_array_elements_tokenized_independently(sample_input, field_types):
    tokens = tokenize(sample_input, field_types)
    pet_tokens = [t for t in tokens if t.origin == "family_and_relationships.pet_names"]
    assert len(pet_tokens) == 2
    assert {t.base for t in pet_tokens} == {"Rocky", "Luna"}


def test_date_full_string_produces_rich_variants(sample_input, field_types):
    tokens = tokenize(sample_input, field_types)
    date_tokens = [t for t in tokens if t.origin == "family_and_relationships.important_dates"]
    assert date_tokens
    variants = set(date_tokens[0].variants)
    assert "14022015" in variants
    assert "2015" in variants


def test_date_non_parseable_degrades(field_types):
    data = {"birth_data": {"day_of_birth": "notadate"}}
    tokens = tokenize(data, field_types)
    assert tokens
    assert tokens[0].variants


def test_write_here_match_is_case_insensitive(field_types):
    data = {"personal_info": {"name": "write here", "nickname": " Write Here ", "last_name": "Ok"}}
    tokens = tokenize(data, field_types)
    origins = _origins(tokens)
    assert origins == {"personal_info.last_name"}


def test_no_spaces_by_default(field_types):
    data = {"address_data": {"childhood_street": "San Martin"}}
    tokens = tokenize(data, field_types)
    assert all(" " not in variant for token in tokens for variant in token.variants)


def test_spaces_kept_when_allowed(field_types):
    data = {"address_data": {"childhood_street": "San Martin"}}
    tokens = tokenize(data, field_types, allow_spaces=True)
    assert any(" " in variant for token in tokens for variant in token.variants)
