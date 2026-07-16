"""Unit tests for :mod:`alphaDeesp.core.topo_applicator`.

Tests the static helpers exposed by TopoApplicatorMixin which do not depend
on self.g or the full AlphaDeesp pipeline.
"""

import pytest
from alphaDeesp.core.topo_applicator import TopoApplicatorMixin
from alphaDeesp.core.elements import (
    Consumption,
    ExtremityLine,
    OriginLine,
    Production,
)


# ──────────────────────────────────────────────────────────────────────
# _compute_prod_load_per_bus
# ──────────────────────────────────────────────────────────────────────

class TestComputeProdLoadPerBus:

    def test_single_production(self):
        elements = [Production(busbar_id=0, value=10.0)]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {0: 10.0}
        assert load == {}

    def test_single_consumption(self):
        elements = [Consumption(busbar_id=1, value=5.0)]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {}
        assert load == {1: 5.0}

    def test_mixed_on_same_bus(self):
        elements = [
            Production(busbar_id=0, value=10.0),
            Consumption(busbar_id=0, value=3.0),
        ]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {0: 10.0}
        assert load == {0: 3.0}

    def test_multiple_productions_summed(self):
        elements = [
            Production(busbar_id=0, value=4.0),
            Production(busbar_id=0, value=6.0),
        ]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {0: pytest.approx(10.0)}

    def test_production_on_two_buses(self):
        elements = [
            Production(busbar_id=0, value=8.0),
            Production(busbar_id=1, value=2.0),
        ]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {0: 8.0, 1: 2.0}

    def test_origin_line_ignored(self):
        elements = [OriginLine(busbar_id=0, end_substation_id=2)]
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus(elements)
        assert prod == {}
        assert load == {}

    def test_empty_elements(self):
        prod, load = TopoApplicatorMixin._compute_prod_load_per_bus([])
        assert prod == {}
        assert load == {}


# ──────────────────────────────────────────────────────────────────────
# _classify_bus
# ──────────────────────────────────────────────────────────────────────

class TestClassifyBus:

    def test_prod_only(self):
        kind, value = TopoApplicatorMixin._classify_bus(0, {0: 10.0}, {})
        assert kind == "prod"
        assert value == pytest.approx(10.0)

    def test_load_only(self):
        kind, value = TopoApplicatorMixin._classify_bus(1, {}, {1: 5.0})
        assert kind == "load"
        assert value == pytest.approx(5.0)

    def test_both_prod_dominant(self):
        kind, value = TopoApplicatorMixin._classify_bus(0, {0: 10.0}, {0: 3.0})
        assert kind == "prod"
        assert value == pytest.approx(7.0)

    def test_both_load_dominant(self):
        kind, value = TopoApplicatorMixin._classify_bus(0, {0: 2.0}, {0: 8.0})
        assert kind == "load"
        assert value == pytest.approx(-6.0)

    def test_neither_returns_none(self):
        kind, value = TopoApplicatorMixin._classify_bus(0, {}, {})
        assert kind is None
        assert value == 0

    def test_bus_not_present_returns_none(self):
        kind, value = TopoApplicatorMixin._classify_bus(2, {0: 5.0}, {1: 3.0})
        assert kind is None
        assert value == 0


# ──────────────────────────────────────────────────────────────────────
# apply_new_topo_to_graph — full graph mutation (busbar split)
# ──────────────────────────────────────────────────────────────────────

import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

from alphaDeesp.core.twin_nodes import twin_node_id  # noqa: E402


class _ApplyHost(TopoApplicatorMixin):
    def __init__(self, g, df, sim_data):
        self.g = g
        self.df = df
        self.simulator_data = sim_data
        self.bag_of_graphs = {}
        self.debug = False


class TestApplyNewTopoToGraph:
    def _setup(self):
        g = nx.MultiDiGraph()
        for n in (0, 1, 2):
            g.add_node(n)
        g.add_edge(0, 1, color="blue", name="l01")
        g.add_edge(0, 2, color="coral", name="l02")
        df = pd.DataFrame({"idx_or": [0, 0], "idx_ex": [1, 2], "swapped": [False, False]})
        elements = [
            OriginLine(busbar_id=0, end_substation_id=1, flow_value=[5.0]),
            OriginLine(busbar_id=0, end_substation_id=2, flow_value=[3.0]),
        ]
        sim_data = {"substations_elements": {0: elements}}
        return _ApplyHost(g, df, sim_data), g

    def test_split_rewires_second_element_to_twin_node(self):
        host, g = self._setup()
        new_graph, internal = host.apply_new_topo_to_graph(g, [0, 1], node_to_change=0)
        twin = twin_node_id(0)
        # element 0 stays on node 0, element 1 moves to the twin busbar node
        assert new_graph.has_edge(0, 1)
        assert new_graph.has_edge(twin, 2)
        # original colours are carried over onto the rewired edges
        assert new_graph.edges[(0, 1, 0)]["color"] == "blue"
        assert new_graph.edges[(twin, 2, 0)]["color"] == "coral"
        # the topology is registered in the bag under its encoded name
        assert "0_01" in host.bag_of_graphs
        assert internal[0][1].busbar_id == 1  # second element reassigned to bus 1

    def test_single_bus_topology_keeps_everything_on_node(self):
        host, g = self._setup()
        # all-zero topology: no split, everything stays on node 0
        new_graph, _ = host.apply_new_topo_to_graph(g, [0, 0], node_to_change=0)
        assert new_graph.has_edge(0, 1)
        assert new_graph.has_edge(0, 2)
        assert twin_node_id(0) not in new_graph.nodes
