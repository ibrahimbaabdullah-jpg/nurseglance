"""Checks for the proposed study's sample size and allocation list (docs/protocol.md)."""
from collections import Counter

from analysis.allocation import allocation, half_block, sequence
from analysis.sample_size import n_needed, power


def test_sample_size_matches_standard_tables():
    # Paired t test, two-sided alpha 0.05 (values agree with G*Power).
    assert n_needed(0.5) == 34
    assert n_needed(0.8) == 15
    assert n_needed(0.5, 0.90) == 44
    assert 0.80 <= power(34, 0.5) < 0.82


def test_allocation_balances_every_block_of_eight():
    rows = allocation(40, master_seed=2027)
    assert len(rows) == 40
    assert len({r["seed"] for r in rows}) == 40
    keys = [sequence(r["seed"]) for r in rows]
    assert set(Counter(keys).values()) == {5}
    for start in range(0, 40, 8):
        assert len(set(keys[start:start + 8])) == 8
    assert Counter(r["first_view"] for r in rows) == {"glance": 20, "tabbed": 20}


def test_every_half_block_of_four_is_balanced_so_a_list_per_role_works():
    rows = allocation(20, master_seed=7)          # one role's list: 20 nurses
    keys = [sequence(r["seed"]) for r in rows]
    assert Counter(r["first_view"] for r in rows) == {"glance": 10, "tabbed": 10}
    for start in range(0, 20, 4):
        quad = keys[start:start + 4]
        assert len({half_block(k) for k in quad}) == 1
        for factor in range(3):
            assert set(Counter(k[factor] for k in quad).values()) == {2}
