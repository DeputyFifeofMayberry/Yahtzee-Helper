from collections import Counter
from itertools import product

from yahtzee.advisor import YahtzeeAdvisor
from yahtzee.models import Scorecard
from yahtzee.probabilities import outcome_class_distribution, reroll_distribution


def test_reroll_distribution_matches_bruteforce_for_two_dice():
    exact = reroll_distribution(2)
    brute = Counter(tuple(sorted(outcome)) for outcome in product(range(1, 7), repeat=2))
    total = 36
    assert set(exact.keys()) == set(brute.keys())
    for outcome, count in brute.items():
        assert abs(exact[outcome] - count / total) < 1e-12


def test_outcome_class_distribution_mass_is_one():
    dist = {
        (1, 1, 1, 1, 1): 0.2,
        (2, 3, 4, 5, 6): 0.3,
        (2, 2, 3, 3, 3): 0.5,
    }
    classes = outcome_class_distribution(dist)
    assert abs(sum(classes.values()) - 1.0) < 1e-12


def test_optimal_distribution_mass_is_one():
    advisor = YahtzeeAdvisor()
    sc = Scorecard()
    classes = advisor.optimal_turn_outcome_probabilities((2, 2), 2, sc)
    assert abs(sum(classes.values()) - 1.0) < 1e-9
