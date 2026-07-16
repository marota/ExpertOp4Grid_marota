"""Tests for the null-flow path-search routing weight (issue #1).

``_compute_sssp_paths`` now precomputes an edge-weight attribute and runs
Dijkstra with a string weight (perf), with two modes:

* ``capacity_weighted=False`` (default) — "bless": bit-identical to the old
  per-edge callable, which on a ``MultiDiGraph`` read capacity as ``0`` and never
  matched the ``(u, v, key)`` promoted set, i.e. a uniform hop weight.
* ``capacity_weighted=True`` — "fix": capacity-weighted routing.
"""

import networkx as nx

from alphaDeesp.tests.graphs_test_helpers import DetectEdgesHelperHost


def _prepared_single_source(source):
    """Minimal ``prepared`` dict that lets ``_compute_sssp_paths`` run ``source``."""
    return {
        "source_nodes_in_gc": [source],
        "bfs_cache": {source: True},
        "targets_with_bfs": frozenset(),
        "node_has_incident_interest": {source: True},
        "any_target_has_interest": True,
    }


def _issue_repro_graph():
    # From issue #1: a heavy direct A->C vs a light A->B->C.
    g = nx.MultiDiGraph()
    g.add_edge("A", "B", capacity=1.0, name="ab")
    g.add_edge("B", "C", capacity=2.0, name="bc")
    g.add_edge("A", "C", capacity=10.0, name="ac")
    return g


def _old_callable_sssp(g, source, edges_of_interest):
    """Faithful re-implementation of the pre-refactor per-edge callable weight."""
    promoted_set = set(edges_of_interest)

    def w(u, v, attr):
        real_weight = attr.get("capacity", 0)  # dict-of-keys on a multigraph -> 0
        return real_weight * 1_000_000_000 + (33 if (u, v) in promoted_set else 100)

    return nx.single_source_dijkstra_path(g, source, weight=w)


class TestNullFlowRoutingModes:

    def test_option_A_default_is_hop_only(self):
        obj = DetectEdgesHelperHost()
        g = _issue_repro_graph()
        res = obj._compute_sssp_paths(g, _prepared_single_source("A"), set())
        # hop-only: the 1-hop direct edge wins even though it is "heavier".
        assert res["A"]["C"] == ["A", "C"]

    def test_option_B_is_capacity_weighted(self):
        obj = DetectEdgesHelperHost()
        g = _issue_repro_graph()
        res = obj._compute_sssp_paths(
            g, _prepared_single_source("A"), set(), capacity_weighted=True)
        # capacity 3 (A->B->C) beats 10 (A->C) despite the extra hop.
        assert res["A"]["C"] == ["A", "B", "C"]

    def test_option_A_is_bit_identical_to_old_callable(self):
        # Multigraph with parallel edges and a promoted (u, v, key) set — the
        # exact shape the old callable mishandled. New Option A must match it.
        g = nx.MultiDiGraph()
        g.add_edge("S", "M", capacity=0.0, name="sm")
        g.add_edge("S", "M", capacity=5.0, name="sm2")   # parallel edge
        g.add_edge("M", "T", capacity=0.0, name="mt")
        g.add_edge("S", "X", capacity=0.0, name="sx")
        g.add_edge("X", "T", capacity=0.0, name="xt")
        edges_of_interest = {("M", "T", 0)}  # a (u, v, key) triple

        obj = DetectEdgesHelperHost()
        new_a = obj._compute_sssp_paths(
            g.copy(), _prepared_single_source("S"), edges_of_interest)
        old = _old_callable_sssp(g.copy(), "S", edges_of_interest)
        assert new_a["S"] == old

    def test_option_B_promoted_key_tuple_is_matched(self):
        # Two equal-capacity routes S->A->T and S->B->T; promote the B route by
        # its exact (u, v, key). Option B must prefer it via the lower hop cost.
        g = nx.MultiDiGraph()
        g.add_edge("S", "A", capacity=1.0, name="sa")
        g.add_edge("A", "T", capacity=1.0, name="at")
        kb1 = g.add_edge("S", "B", capacity=1.0, name="sb")
        kb2 = g.add_edge("B", "T", capacity=1.0, name="bt")
        promoted = {("S", "B", kb1), ("B", "T", kb2)}
        obj = DetectEdgesHelperHost()
        res = obj._compute_sssp_paths(
            g, _prepared_single_source("S"), promoted, capacity_weighted=True)
        assert res["S"]["T"] == ["S", "B", "T"]
