"""Unit tests for :class:`OverflowGraphRenderer`.

The renderer holds all Graphviz *presentation* logic extracted from
``OverFlowGraph``. These tests exercise it standalone (on bare graphs) to
prove the model/renderer split leaves the rendering reusable in isolation —
the reason downstream repositories can depend on it directly.
"""

import networkx as nx
import pandas as pd

from alphaDeesp.core.graphs.overflow_renderer import OverflowGraphRenderer
# The renderer must also be reachable through both public surfaces.
from alphaDeesp.core.graphs import OverflowGraphRenderer as _FromPackage
from alphaDeesp.core.graphsAndPaths import OverflowGraphRenderer as _FromShim


class TestPublicSurface:
    def test_exported_from_package_and_shim(self):
        assert _FromPackage is OverflowGraphRenderer
        assert _FromShim is OverflowGraphRenderer


class TestPenwidthScaling:
    def test_scaling_factor_and_visibility_floor(self):
        scaling, min_pen = OverflowGraphRenderer.penwidth_scaling(
            pd.Series([1000.0, 100.0, 10.0]))
        assert scaling == 15.0 / 1000.0
        # floor = max(1 MW * 0.015, 10% * 15) = max(0.015, 1.5) = 1.5
        assert abs(min_pen - 1.5) < 1e-9

    def test_all_zero_flow_falls_back_to_unit_scale(self):
        scaling, min_pen = OverflowGraphRenderer.penwidth_scaling(pd.Series([0.0]))
        assert scaling == 1.0
        assert min_pen == 1.5

    def test_edge_penwidth_is_clamped_to_floor(self):
        # tiny flow (10 MW) at the 1000-MW scale -> 0.15 raw, clamped to 1.5
        pen = OverflowGraphRenderer.edge_penwidth(
            10.0, scaling_factor=0.015, min_penwidth=1.5, float_precision="%.2f")
        assert pen == 1.5

    def test_edge_penwidth_scales_when_above_floor(self):
        pen = OverflowGraphRenderer.edge_penwidth(
            1000.0, scaling_factor=0.015, min_penwidth=1.5, float_precision="%.2f")
        assert pen == 15.0


class TestNodeShapes:
    def test_set_hub_shapes_only_marks_hubs(self):
        g = nx.MultiDiGraph()
        g.add_node("A")
        g.add_node("B")
        OverflowGraphRenderer.set_hub_shapes(g, ["A"], shape_hub="diamond")
        assert g.nodes["A"]["shape"] == "diamond"
        assert g.nodes["B"]["shape"] == "oval"

    def test_collapse_red_loops_collapses_pure_coral_oval(self):
        g = nx.MultiDiGraph()
        g.add_node("N1", shape="oval")
        g.add_edge("N1", "N2", color="coral")
        OverflowGraphRenderer.collapse_red_loops(g)
        assert g.nodes["N1"]["shape"] == "point"

    def test_collapse_red_loops_leaves_mixed_node_alone(self):
        g = nx.MultiDiGraph()
        g.add_node("N1", shape="oval")
        g.add_edge("N1", "N2", color="coral")
        g.add_edge("N1", "N3", color="blue")
        OverflowGraphRenderer.collapse_red_loops(g)
        assert g.nodes["N1"]["shape"] == "oval"


class TestSwappedFlowStyling:
    def test_swapped_lines_get_tapered_style(self):
        g = nx.MultiDiGraph()
        g.add_edge("A", "B", name="L1", color="coral")
        g.add_edge("B", "C", name="L2", color="blue")
        OverflowGraphRenderer.highlight_swapped_flows(g, ["L1"])
        l1 = g.edges[("A", "B", 0)]
        l2 = g.edges[("B", "C", 0)]
        assert l1["style"] == "tapered" and l1["dir"] == "both" and l1["arrowtail"] == "none"
        assert "style" not in l2


class TestHighlightFormatting:
    def test_compound_highlight_color(self):
        assert OverflowGraphRenderer.highlight_color("black") == '"black:yellow:black"'
        assert OverflowGraphRenderer.highlight_color("coral") == '"coral:yellow:coral"'

    def test_overload_label_emphasises_before(self):
        label = OverflowGraphRenderer.overload_label("x", 110, 80)
        assert "<B>110%</B>" in label and "80%" in label

    def test_low_margin_label_emphasises_after(self):
        label = OverflowGraphRenderer.low_margin_label("x", 90, 0)
        assert "90% → <B>0%</B>" in label
