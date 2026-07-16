"""Unit tests for :class:`GraphConsolidationMixin`.

These consolidation helpers (edge reversal, loop-path recolouring, ambiguity
classification) were previously exercised only by the grid2op integration
suite. Here they run on small hand-built coloured graphs, no grid2op needed.
"""

import networkx as nx

from alphaDeesp.core.graphs.graph_consolidation import GraphConsolidationMixin
from alphaDeesp.core.graphs.constrained_path import ConstrainedPath


class _ConsolidationHost(GraphConsolidationMixin):
    """Minimal host exposing the mixin with the attributes it assumes."""

    def __init__(self, g, float_precision="%.2f"):
        self.g = g
        self.float_precision = float_precision


def _edge(g, name):
    for u, v, k, d in g.edges(keys=True, data=True):
        if d.get("name") == name:
            return (u, v, k), d
    raise AssertionError(f"edge {name!r} not found")


# ──────────────────────────────────────────────────────────────────────
# _is_ambiguous_component
# ──────────────────────────────────────────────────────────────────────

class TestIsAmbiguousComponent:
    def _comp(self, *edges):
        g = nx.MultiDiGraph()
        for u, v, color in edges:
            g.add_edge(u, v, color=color)
        return g, set(g.nodes)

    def test_blue_and_coral_two_colours_is_ambiguous(self):
        g, comp = self._comp(("A", "B", "blue"), ("B", "A", "coral"))
        assert GraphConsolidationMixin._is_ambiguous_component(g, comp) is True

    def test_single_node_is_not_ambiguous(self):
        g = nx.MultiDiGraph()
        g.add_node("A")
        assert GraphConsolidationMixin._is_ambiguous_component(g, {"A"}) is False

    def test_three_colours_is_not_ambiguous(self):
        g, comp = self._comp(("A", "B", "blue"), ("B", "C", "coral"), ("C", "A", "black"))
        assert GraphConsolidationMixin._is_ambiguous_component(g, comp) is False

    def test_single_colour_is_not_ambiguous(self):
        g, comp = self._comp(("A", "B", "blue"), ("B", "C", "blue"))
        assert GraphConsolidationMixin._is_ambiguous_component(g, comp) is False


# ──────────────────────────────────────────────────────────────────────
# reverse_edges
# ──────────────────────────────────────────────────────────────────────

class TestReverseEdges:
    def test_reverses_direction_flips_capacity_and_recolours(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="L1", color="blue", capacity=-5.0, label="-5.00")
        host = _ConsolidationHost(g)
        host.reverse_edges(["L1"], target_color="coral")

        # original A->B is gone; reversed B->A exists
        assert not host.g.has_edge("A", "B")
        (key, data) = _edge(host.g, "L1")
        assert key[:2] == ("B", "A")
        assert data["color"] == "coral"
        assert data["capacity"] == 5.0
        assert data["label"] == "5.00"

    def test_edge_already_target_colour_is_not_flipped(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="L1", color="coral", capacity=3.0, label="3.00")
        host = _ConsolidationHost(g)
        host.reverse_edges(["L1"], target_color="coral")
        # same colour -> stays A->B, capacity unchanged (no reversal)
        assert host.g.has_edge("A", "B")
        _, data = _edge(host.g, "L1")
        assert data["capacity"] == 3.0


# ──────────────────────────────────────────────────────────────────────
# consolidate_loop_path
# ──────────────────────────────────────────────────────────────────────

class TestConsolidateLoopPath:
    def test_gray_edges_on_hub_path_become_coral(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="ab", color="gray", capacity=5.0)
        g.add_edge("B", "C", name="bc", color="gray", capacity=5.0)
        host = _ConsolidationHost(g)
        host.consolidate_loop_path(["A"], ["C"])
        assert _edge(host.g, "ab")[1]["color"] == "coral"
        assert _edge(host.g, "bc")[1]["color"] == "coral"

    def test_null_capacity_edges_are_ignored(self):
        g = nx.MultiDiGraph()
        # zero-capacity gray edges are dropped from the search graph
        g.add_edge("A", "B", name="ab", color="gray", capacity=0.0)
        g.add_edge("B", "C", name="bc", color="gray", capacity=0.0)
        host = _ConsolidationHost(g)
        host.consolidate_loop_path(["A"], ["C"])
        assert _edge(host.g, "ab")[1]["color"] == "gray"
        assert _edge(host.g, "bc")[1]["color"] == "gray"

    def test_non_gray_edges_on_path_are_left_alone(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="ab", color="black", capacity=5.0)
        g.add_edge("B", "C", name="bc", color="gray", capacity=5.0)
        host = _ConsolidationHost(g)
        host.consolidate_loop_path(["A"], ["C"])
        assert _edge(host.g, "ab")[1]["color"] == "black"   # unchanged
        assert _edge(host.g, "bc")[1]["color"] == "coral"   # gray -> coral


# ──────────────────────────────────────────────────────────────────────
# reverse_blue_edges_in_looppaths
# ──────────────────────────────────────────────────────────────────────

class TestReverseBlueEdgesInLoopPaths:
    def test_blue_edge_off_constrained_path_is_reversed_to_coral(self):
        g = nx.MultiDiGraph()
        g.add_edge("X", "Y", name="xy", color="blue", capacity=-5.0, label="-5.00")
        host = _ConsolidationHost(g)
        host.reverse_blue_edges_in_looppaths(constrained_path=[])
        assert not host.g.has_edge("X", "Y")
        (key, data) = _edge(host.g, "xy")
        assert key[:2] == ("Y", "X")
        assert data["color"] == "coral"
        assert data["capacity"] == 5.0

    def test_edge_on_constrained_path_is_untouched(self):
        g = nx.MultiDiGraph()
        g.add_edge("X", "Y", name="xy", color="blue", capacity=-5.0, label="-5.00")
        host = _ConsolidationHost(g)
        # X on the constrained path -> its incident blue edge is excluded
        host.reverse_blue_edges_in_looppaths(constrained_path=["X"])
        assert host.g.has_edge("X", "Y")
        _, data = _edge(host.g, "xy")
        assert data["color"] == "blue"


# ──────────────────────────────────────────────────────────────────────
# desambiguation_type_path
# ──────────────────────────────────────────────────────────────────────

class _FakeStructured:
    def __init__(self, constrained_path):
        self.constrained_path = constrained_path


class TestDesambiguationTypePath:
    def _structured(self):
        cp = ConstrainedPath(
            amont_edges=[("A", "B", 0)],
            constrained_edge=("B", "C", 0),
            aval_edges=[("C", "D", 0)],
        )
        return _FakeStructured(cp)

    def test_fewer_than_two_cpath_nodes_is_loop_path(self):
        host = _ConsolidationHost(nx.MultiDiGraph())
        assert host.desambiguation_type_path(["A"], self._structured()) == "loop_path"

    def test_amont_only_is_constrained_path(self):
        host = _ConsolidationHost(nx.MultiDiGraph())
        # A and B are both amont -> connects amont but not aval
        assert host.desambiguation_type_path(["A", "B"], self._structured()) == "constrained_path"

    def test_bridging_amont_and_aval_is_loop_path(self):
        host = _ConsolidationHost(nx.MultiDiGraph())
        # B (amont) and C (aval) -> bridges both sides
        assert host.desambiguation_type_path(["B", "C"], self._structured()) == "loop_path"
