from yahtzee.rules import is_full_house, is_large_straight, is_n_of_a_kind, is_small_straight


def test_full_house_detected():
    assert is_full_house((2, 2, 3, 3, 3))
    assert not is_full_house((2, 2, 2, 2, 3))


def test_straights_with_duplicates():
    assert is_small_straight((1, 2, 3, 4, 4))
    assert is_small_straight((2, 3, 3, 4, 5))
    assert not is_large_straight((1, 2, 3, 4, 4))
    assert is_large_straight((2, 3, 4, 5, 6))


def test_kind_logic():
    assert is_n_of_a_kind((6, 6, 6, 2, 1), 3)
    assert not is_n_of_a_kind((6, 6, 2, 1, 3), 3)
