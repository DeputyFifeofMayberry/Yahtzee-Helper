import pytest

from yahtzee.input_parsing import dice_from_face_counts, face_counts_from_dice, parse_quick_dice_entry


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("11116", [1, 1, 1, 1, 6]),
        ("1 1 1 1 6", [1, 1, 1, 1, 6]),
        ("1,1,1,1,6", [1, 1, 1, 1, 6]),
        ("1, 1, 1, 1, 6", [1, 1, 1, 1, 6]),
    ],
)
def test_parse_quick_dice_entry_accepts_supported_formats(raw: str, expected: list[int]):
    assert parse_quick_dice_entry(raw) == expected


def test_parse_quick_dice_entry_rejects_too_few_dice():
    with pytest.raises(ValueError, match="Enter exactly 5 dice values"):
        parse_quick_dice_entry("1 1 1 6")


def test_parse_quick_dice_entry_rejects_too_many_dice():
    with pytest.raises(ValueError, match="Enter exactly 5 dice values"):
        parse_quick_dice_entry("1 1 1 1 1 6")


def test_parse_quick_dice_entry_rejects_zero():
    with pytest.raises(ValueError, match="between 1 and 6"):
        parse_quick_dice_entry("0 1 1 1 6")


def test_parse_quick_dice_entry_rejects_seven():
    with pytest.raises(ValueError, match="between 1 and 6"):
        parse_quick_dice_entry("1 1 1 1 7")


def test_parse_quick_dice_entry_rejects_letters():
    with pytest.raises(ValueError, match="Use only digits, spaces, or commas"):
        parse_quick_dice_entry("1 1 a 1 6")


def test_parse_quick_dice_entry_rejects_mixed_garbage_punctuation():
    with pytest.raises(ValueError, match="Use only digits, spaces, or commas"):
        parse_quick_dice_entry("1;1/1?1!6")


def test_dice_from_face_counts_converts_valid_counts():
    assert dice_from_face_counts([4, 0, 0, 0, 0, 1]) == [1, 1, 1, 1, 6]
    assert dice_from_face_counts({1: 4, 2: 0, 3: 0, 4: 0, 5: 0, 6: 1}) == [1, 1, 1, 1, 6]


def test_dice_from_face_counts_rejects_totals_not_equal_to_five():
    with pytest.raises(ValueError, match="total exactly 5"):
        dice_from_face_counts([1, 1, 1, 0, 0, 0])


def test_dice_from_face_counts_rejects_negative_counts():
    with pytest.raises(ValueError, match="non-negative"):
        dice_from_face_counts([4, -1, 0, 0, 0, 2])


def test_face_counts_from_dice_returns_expected_counts():
    assert face_counts_from_dice([1, 1, 1, 1, 6]) == [4, 0, 0, 0, 0, 1]
