"""Backwards-compatible shim for :mod:`alphaDeesp.core.graphsAndPaths`.

The original monolithic module has been split into the focused package
:mod:`alphaDeesp.core.graphs`. All public names are re-exported here so
existing imports such as::

    from alphaDeesp.core.graphsAndPaths import OverFlowGraph, ConstrainedPath

continue to work unchanged. New code should prefer importing directly
from :mod:`alphaDeesp.core.graphs` (or one of its sub-modules).
"""

from alphaDeesp.core.graphs import (  # noqa: F401
    EDGE_ROLE_INSIGNIFICANT,
    EDGE_ROLE_NEGATIVE,
    EDGE_ROLE_NULL_NON_RECONNECTABLE,
    EDGE_ROLE_OVERLOAD,
    EDGE_ROLE_POSITIVE,
    EDGE_ROLE_UNKNOWN,
    ConstrainedPath,
    OverFlowGraph,
    OverflowGraphRenderer,
    PowerFlowGraph,
    Structured_Overload_Distribution_Graph,
    add_double_edges_null_redispatch,
    all_simple_edge_paths_multi,
    base_color_of,
    default_voltage_colors,
    delete_color_edges,
    edge_role_of,
    find_multidigraph_edges_by_name,
    from_edges_get_nodes,
    incident_edges,
    nodepath_to_edgepath,
    remove_unused_added_double_edge,
    shortest_path_mandatory_and_promoted,
    shortest_path_min_weight_then_hops,
    shortest_path_with_promoted_edges,
)

__all__ = [
    "default_voltage_colors",
    "PowerFlowGraph",
    "OverFlowGraph",
    "OverflowGraphRenderer",
    "ConstrainedPath",
    "Structured_Overload_Distribution_Graph",
    "edge_role_of",
    "base_color_of",
    "EDGE_ROLE_OVERLOAD",
    "EDGE_ROLE_NEGATIVE",
    "EDGE_ROLE_POSITIVE",
    "EDGE_ROLE_INSIGNIFICANT",
    "EDGE_ROLE_NULL_NON_RECONNECTABLE",
    "EDGE_ROLE_UNKNOWN",
    "from_edges_get_nodes",
    "delete_color_edges",
    "nodepath_to_edgepath",
    "incident_edges",
    "all_simple_edge_paths_multi",
    "find_multidigraph_edges_by_name",
    "add_double_edges_null_redispatch",
    "remove_unused_added_double_edge",
    "shortest_path_min_weight_then_hops",
    "shortest_path_mandatory_and_promoted",
    "shortest_path_with_promoted_edges",
]
