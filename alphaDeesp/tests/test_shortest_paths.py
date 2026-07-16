"""Unit tests for the shortest-path helpers in
:mod:`alphaDeesp.core.graphs.shortest_paths`."""

import networkx as nx

from alphaDeesp.core.graphsAndPaths import (
    shortest_path_with_promoted_edges,
    shortest_path_min_weight_then_hops,
)


class TestShortestPathWithPromotedEdges:

    def test_basic_shortest_path(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", capacity=0)
        g.add_edge("B", "C", capacity=0)
        path, cost = shortest_path_with_promoted_edges(g, "A", "C", [], weight_attr="capacity")
        assert path == ["A", "B", "C"]
        assert cost == 0

    def test_no_path_returns_none(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", capacity=0)
        g.add_edge("C", "D", capacity=0)
        path, cost = shortest_path_with_promoted_edges(g, "A", "D", [], weight_attr="capacity")
        assert path is None
        assert cost == float("inf")

    def test_prefers_lower_weight(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", capacity=0)
        g.add_edge("B", "C", capacity=0)
        g.add_edge("A", "C", capacity=10)  # direct but heavy
        path, cost = shortest_path_with_promoted_edges(g, "A", "C", [], weight_attr="capacity")
        assert path == ["A", "B", "C"]
        assert cost == 0

    def test_with_promoted_edges(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", capacity=0)
        g.add_edge("B", "D", capacity=0)
        g.add_edge("A", "C", capacity=0)
        g.add_edge("C", "D", capacity=0)
        path, _ = shortest_path_with_promoted_edges(
            g, "A", "D", promoted_edges=[("A", "C")], weight_attr="capacity")
        assert path == ["A", "C", "D"]

    def test_single_node_path(self):
        g = nx.DiGraph()
        g.add_node("A")
        path, _ = shortest_path_with_promoted_edges(g, "A", "A", [], weight_attr="capacity")
        assert path == ["A"]


class TestShortestPathMinWeightThenHops:

    def test_basic_path_through_mandatory_edge(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", weight=1)
        g.add_edge("B", "C", weight=1)
        g.add_edge("C", "D", weight=1)
        path, cost = shortest_path_min_weight_then_hops(
            g, "A", "D", mandatory_edge=("B", "C"), weight_attr="weight")
        assert "B" in path
        assert "C" in path
        assert cost == 3

    def test_no_path_returns_none(self):
        g = nx.DiGraph()
        g.add_edge("A", "B", weight=1)
        g.add_edge("C", "D", weight=1)
        path, cost = shortest_path_min_weight_then_hops(
            g, "A", "D", mandatory_edge=("A", "B"), weight_attr="weight")
        assert path is None
        assert cost == float("inf")

    def test_multigraph_with_key(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", weight=5)
        k1 = g.add_edge("A", "B", weight=1)
        g.add_edge("B", "C", weight=1)
        path, cost = shortest_path_min_weight_then_hops(
            g, "A", "C", mandatory_edge=("A", "B", k1), weight_attr="weight")
        assert path is not None
        assert cost == 2  # key k1 (1) + B->C (1)


# ──────────────────────────────────────────────────────────────────────
# MultiDiGraph handling: networkx passes the {key: attr} view of parallel
# edges to a callable weight. The old closures did attr.get(weight) and read
# 0 for every multigraph edge; the shared factory now takes the min parallel
# weight and matches promoted (u, v) OR (u, v, key).
# ──────────────────────────────────────────────────────────────────────

from alphaDeesp.core.graphsAndPaths import shortest_path_mandatory_and_promoted  # noqa: E402


class TestMultiDiGraphWeighting:

    def test_min_weight_path_chosen_on_multigraph(self):
        g = nx.MultiDiGraph()
        # Direct A->C is heavy; the A->B->C route is light. With the old bug all
        # weights read 0, so the (shorter-hop) direct edge would win wrongly.
        g.add_edge("A", "C", weight=100.0)
        g.add_edge("A", "B", weight=1.0)
        g.add_edge("B", "C", weight=1.0)
        path, total = shortest_path_with_promoted_edges(
            g, "A", "C", promoted_edges=[], weight_attr="weight")
        assert path == ["A", "B", "C"]
        assert total == 2.0

    def test_parallel_edges_use_min_weight(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", weight=50.0)
        g.add_edge("A", "B", weight=2.0)   # cheaper parallel edge
        g.add_edge("A", "X", weight=3.0)
        g.add_edge("X", "B", weight=3.0)
        # Cheapest A->B is the 2.0 parallel edge (< 3+3 via X).
        path, total = shortest_path_with_promoted_edges(
            g, "A", "B", promoted_edges=[], weight_attr="weight")
        assert path == ["A", "B"]
        assert total == 2.0

    def test_promoted_key_tuple_matches_on_multigraph(self):
        g = nx.MultiDiGraph()
        # Two equal-weight amont routes; promote the B-route by (u, v, key).
        g.add_edge("S", "A", weight=1.0)
        g.add_edge("A", "M1", weight=1.0)
        kb1 = g.add_edge("S", "B", weight=1.0)
        kb2 = g.add_edge("B", "M1", weight=1.0)
        g.add_edge("M1", "M2", weight=1.0)
        g.add_edge("M2", "T", weight=1.0)
        path, _ = shortest_path_mandatory_and_promoted(
            g, "S", "T", mandatory_edge=("M1", "M2"),
            promoted_edges=[("S", "B", kb1), ("B", "M1", kb2)],
            weight_attr="weight")
        assert path == ["S", "B", "M1", "M2", "T"]
