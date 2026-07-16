"""Unit tests for :mod:`alphaDeesp.core.graphs.edge_roles`.

The role accessor is the single authority that maps an edge's base colour to a
semantic role, so consumers never parse Graphviz colour strings.
"""

from alphaDeesp.core.graphs.edge_roles import (
    EDGE_ROLE_INSIGNIFICANT,
    EDGE_ROLE_NEGATIVE,
    EDGE_ROLE_NULL_NON_RECONNECTABLE,
    EDGE_ROLE_OVERLOAD,
    EDGE_ROLE_POSITIVE,
    EDGE_ROLE_UNKNOWN,
    base_color_of,
    edge_role_of,
)
# also reachable via both public surfaces
from alphaDeesp.core.graphs import edge_role_of as _from_pkg
from alphaDeesp.core.graphsAndPaths import edge_role_of as _from_shim


class TestPublicSurface:
    def test_exported_from_package_and_shim(self):
        assert _from_pkg is edge_role_of
        assert _from_shim is edge_role_of


class TestEdgeRoleOf:
    def test_clean_base_colours_map_to_roles(self):
        assert edge_role_of({"color": "black"}) == EDGE_ROLE_OVERLOAD
        assert edge_role_of({"color": "blue"}) == EDGE_ROLE_NEGATIVE
        assert edge_role_of({"color": "coral"}) == EDGE_ROLE_POSITIVE
        assert edge_role_of({"color": "gray"}) == EDGE_ROLE_INSIGNIFICANT
        assert edge_role_of({"color": "dimgray"}) == EDGE_ROLE_NULL_NON_RECONNECTABLE

    def test_unknown_colour_is_unknown(self):
        assert edge_role_of({"color": "chartreuse"}) == EDGE_ROLE_UNKNOWN
        assert edge_role_of({}) == EDGE_ROLE_UNKNOWN

    def test_compound_colour_is_stripped(self):
        # After highlight the rendered colour is a compound string.
        assert edge_role_of({"color": '"coral:yellow:coral"'}) == EDGE_ROLE_POSITIVE
        assert edge_role_of({"color": '"black:yellow:black"'}) == EDGE_ROLE_OVERLOAD

    def test_base_color_attribute_is_authoritative(self):
        # base_color wins over a (compound) rendered color.
        data = {"color": '"coral:yellow:coral"', "base_color": "blue"}
        assert base_color_of(data) == "blue"
        assert edge_role_of(data) == EDGE_ROLE_NEGATIVE

    def test_non_string_colour_is_safe(self):
        assert base_color_of({"color": 123}) == ""
        assert edge_role_of({"color": None}) == EDGE_ROLE_UNKNOWN
