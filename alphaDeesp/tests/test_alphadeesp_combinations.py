"""Unit tests for the pure combinatorial / result-shaping helpers of
:class:`alphaDeesp.core.alphadeesp.AlphaDeesp` — busbar-combination
enumeration, legality filtering, best-topology cleanup and constrained-path
flattening. These do not need the full ranking pipeline (no grid2op)."""

import pandas as pd
import pytest

from alphaDeesp.core.alphadeesp import AlphaDeesp
from alphaDeesp.core.elements import OriginLine


class _Host:
    compute_all_combinations = AlphaDeesp.compute_all_combinations
    legal_comb = AlphaDeesp.legal_comb
    clean_and_sort_best_topologies = AlphaDeesp.clean_and_sort_best_topologies
    filter_constrained_path = AlphaDeesp.filter_constrained_path

    def __init__(self, elements=None):
        self.simulator_data = {"substations_elements": {5: elements or []}}


def _lines(n):
    return [OriginLine(busbar_id=0, end_substation_id=i + 1, flow_value=[1.0]) for i in range(n)]


class TestComputeAllCombinations:
    def test_two_elements_returns_the_two_single_bus_configs(self):
        host = _Host(_lines(2))
        assert host.compute_all_combinations(5) == [(1, 1), (0, 0)]

    def test_one_element_raises(self):
        host = _Host(_lines(1))
        with pytest.raises(ValueError):
            host.compute_all_combinations(5)

    def test_five_elements_are_all_legal_and_start_at_bus_zero(self):
        host = _Host(_lines(5))
        combos = host.compute_all_combinations(5)
        assert combos, "expected some legal combinations"
        for c in combos:
            assert c[0] == 0                       # canonical: first element on bus 0
            assert not (all(x == 0 for x in c))    # not the trivial single-bus configs
            assert not (all(x == 1 for x in c))
            assert sum(c) not in (1, len(c) - 1)   # no isolated single element


class TestLegalComb:
    def test_rejects_comb_not_starting_at_zero(self):
        assert _Host().legal_comb([1, 0, 0], 0, 3, [0, 0, 0], [1, 1, 1]) is False

    def test_rejects_the_reference_and_symmetric_configs(self):
        assert _Host().legal_comb([0, 0, 1], 0, 3, [0, 0, 1], [1, 1, 0]) is False  # == config

    def test_rejects_single_element_split(self):
        # sum == 1 (or n-1) means one element alone on a busbar
        assert _Host().legal_comb([0, 1, 0, 0, 0], 0, 5, [0, 0, 0, 0, 0], [1, 1, 1, 1, 1]) is False

    def test_accepts_a_balanced_split(self):
        assert _Host().legal_comb([0, 0, 1, 1, 0], 0, 5, [0, 0, 0, 0, 0], [1, 1, 1, 1, 1]) is True


class TestCleanAndSortBestTopologies:
    def test_drops_sentinel_and_sorts_by_score_desc(self):
        host = _Host()
        df = pd.DataFrame({
            "score": ["XX", 1, 3, 2],
            "topology": [["X"], [0, 1], [1, 0], [1, 1]],
            "node": ["X", 5, 5, 5],
        })
        result = host.clean_and_sort_best_topologies(df)
        assert list(result.index) == [3, 2, 1]   # sentinel "XX" dropped, sorted desc


class TestFilterConstrainedPath:
    def test_flattens_edge_pairs_to_unique_ordered_nodes(self):
        host = _Host()
        assert host.filter_constrained_path([("A", "B"), ("B", "C")]) == ["A", "B", "C"]

    def test_flattens_nested_tuple_edges(self):
        host = _Host()
        assert host.filter_constrained_path([(("A", "B"), ("C", "D"))]) == ["A", "B", "C", "D"]
