import pytest
import typer

from cli import (
    DEFAULT_SYMBOL_POOL,
    SC_SENTINEL,
    _normalize_sc_argv,
    _resolve_special_chars,
)


def test_special_chars_absent():
    assert _resolve_special_chars(None) == (False, [])


def test_special_chars_bare_uses_default_pool():
    present, pool = _resolve_special_chars(SC_SENTINEL)
    assert present is True
    assert pool == DEFAULT_SYMBOL_POOL


def test_special_chars_custom_set():
    present, pool = _resolve_special_chars("$,!,@,%")
    assert present is True
    assert pool == ["$", "!", "@", "%"]


def test_special_chars_dedup():
    _, pool = _resolve_special_chars("!,!,@")
    assert pool == ["!", "@"]


def test_special_chars_dash_symbol_is_valid():
    _, pool = _resolve_special_chars("-,@")
    assert pool == ["-", "@"]


@pytest.mark.parametrize("bad", ["a,!", "1,!", "!!,@", "!, @", "", "!;@"])
def test_special_chars_invalid_format_raises(bad):
    with pytest.raises(typer.BadParameter):
        _resolve_special_chars(bad)


def test_normalize_bare_sc_at_end():
    argv = ["RECH.py", "-p", "gamer", "-sc"]
    _normalize_sc_argv(argv)
    assert argv[-1] == f"--special-chars={SC_SENTINEL}"


def test_normalize_bare_sc_before_another_flag():
    argv = ["RECH.py", "-sc", "-s", "small"]
    _normalize_sc_argv(argv)
    assert argv[1] == f"--special-chars={SC_SENTINEL}"


def test_normalize_sc_with_value_untouched():
    argv = ["RECH.py", "-sc", "$,!", "-s", "small"]
    _normalize_sc_argv(argv)
    assert argv[1] == "-sc"
    assert argv[2] == "$,!"
