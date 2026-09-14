"""Keysyms describe characters; keycodes describe positions.

The distinction is not academic: typing by keycode on the AZERTY layout this was
developed on turns "ASAP 42" into "QSQP 'é". The portal backend therefore types by
keysym, and only modifiers and named keys fall back to positions.
"""
import pytest

from wayland_mcp.backends.keycodes import (
    KEYSYMS,
    code_for_name,
    evdev_keycode,
    keysym_for,
    keysym_for_char,
    parse_combo,
    parse_keysym_combo,
)


# --------------------------------------------------------------------------
# Keysyms: layout independent
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "char, expected",
    [
        ("a", 0x61),
        ("A", 0x41),
        ("4", 0x34),
        (" ", 0x20),
        ("!", 0x21),
        ("é", 0xE9),          # latin-1, so its own codepoint
        ("€", 0x01000000 + 0x20AC),  # outside latin-1, Unicode range
        ("\n", KEYSYMS["enter"]),
        ("\t", KEYSYMS["tab"]),
    ],
)
def test_keysym_for_char(char, expected):
    assert keysym_for_char(char) == expected


def test_case_is_preserved_as_distinct_keysyms():
    """The bug this replaced lowercased everything before typing."""
    assert keysym_for_char("a") != keysym_for_char("A")


def test_named_keys_resolve_to_function_keysyms():
    assert keysym_for("enter") == 0xFF0D
    assert keysym_for("f5") == 0xFFC2
    assert keysym_for("ctrl") == 0xFFE3
    assert keysym_for("nonsense") is None


def test_parse_keysym_combo_splits_modifiers_from_the_key():
    modifiers, main = parse_keysym_combo("ctrl+shift+a")
    assert modifiers == [KEYSYMS["ctrl"], KEYSYMS["shift"]]
    assert main == 0x61


def test_parse_keysym_combo_names_the_key_it_cannot_resolve():
    with pytest.raises(ValueError) as excinfo:
        parse_keysym_combo("ctrl+nonsense")
    assert "nonsense" in str(excinfo.value)


def test_a_bare_key_has_no_modifiers():
    assert parse_keysym_combo("enter") == ([], 0xFF0D)


# --------------------------------------------------------------------------
# Keycodes: positions, for evemu and ydotool
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "char, code, shift",
    [
        ("a", 30, False),
        ("A", 30, True),
        ("1", 2, False),
        ("!", 2, True),
        (" ", 57, False),
        ("enter", 28, False),
        ("f5", 63, False),
    ],
)
def test_evdev_keycode(char, code, shift):
    assert evdev_keycode(char) == (code, shift)


def test_a_character_with_no_us_position_is_reported_as_unknown():
    """Better to skip a character than to type a different one."""
    assert evdev_keycode("é") == (None, False)


def test_shift_is_implied_for_uppercase_and_shifted_punctuation():
    assert parse_combo("A") == ([code_for_name("KEY_LEFTSHIFT")], 30)
    assert parse_combo("?") == ([code_for_name("KEY_LEFTSHIFT")], 53)


def test_parse_combo_keeps_modifier_order():
    assert parse_combo("ctrl+alt+delete") == (
        [code_for_name("KEY_LEFTCTRL"), code_for_name("KEY_LEFTALT")],
        code_for_name("KEY_DELETE"),
    )


def test_parse_combo_names_the_key_it_cannot_resolve():
    with pytest.raises(ValueError) as excinfo:
        parse_combo("ctrl+nope")
    assert "nope" in str(excinfo.value)
