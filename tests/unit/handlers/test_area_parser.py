"""Unit tests for shared.utils.area_parser.parse_area."""
import pytest

from shared.utils.area_parser import parse_area

# ── Dimension pair — symbol separators ────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("2*2",        4.0),
    ("2 * 2",      4.0),
    ("2x2",        4.0),
    ("2 x 2",      4.0),
    ("2×2",        4.0),
    ("3.5x4",      14.0),
    ("3,5 x 4",    14.0),
    ("5 * 3",      15.0),
    ("10X10",      100.0),
])
def test_symbol_separators(text: str, expected: float) -> None:
    assert parse_area(text) == expected


# ── Dimension pair — word separators ──────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("2 ga 2",     4.0),
    ("2ga2",       4.0),
    ("2 dan 2",    4.0),
    ("2dan2",      4.0),
    ("2 by 2",     4.0),
    ("5 ga 4",     20.0),
    ("3,5 ga 4",   14.0),
])
def test_word_separators(text: str, expected: float) -> None:
    assert parse_area(text) == expected


# ── Single value + unit ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("30kv",              30.0),
    ("30 kv",             30.0),
    ("30kvadrat",         30.0),
    ("30 kvadrat",        30.0),
    ("30 kvadrat metr",   30.0),
    ("30m2",              30.0),
    ("30 m2",             30.0),
    ("30 m 2",            30.0),
    ("30m²",              30.0),
    ("30 metr kvadrat",   30.0),
    ("30 квадрат",        30.0),
    ("30 кв",             30.0),
    ("30 кв.м",           30.0),
    ("30кв",              30.0),
    ("30квм",             30.0),
    ("12.5 kv",           12.5),
    ("12,5 m2",           12.5),
])
def test_single_value_with_unit(text: str, expected: float) -> None:
    assert parse_area(text) == expected


# ── Explicitly NOT matched ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "2/2",        # slash excluded
    "2 2",        # bare space excluded
    "hello",      # no number
    "abc",        # no number
    "",           # empty
    "0 kv",       # zero area
    "-5 m2",      # negative (not a valid number token in regex)
])
def test_not_matched(text: str) -> None:
    assert parse_area(text) is None


# ── Bounds ─────────────────────────────────────────────────────────────────────

def test_max_area_accepted() -> None:
    assert parse_area("10000 kv") == 10000.0

def test_above_max_rejected() -> None:
    assert parse_area("10001 kv") is None

def test_rounding() -> None:
    result = parse_area("3.333 x 3")
    assert result == 10.0   # round(9.999, 2) = 10.0

def test_decimal_comma_in_dims() -> None:
    assert parse_area("3,5x4") == 14.0

def test_dimension_priority_over_unit() -> None:
    # "5x4 m2" — dimension pair takes priority
    result = parse_area("5x4 m2")
    assert result == 20.0
