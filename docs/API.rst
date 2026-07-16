*************
API reference
*************

Auto-generated from the source docstrings. See :doc:`ARCHITECTURE` for how these
pieces fit together.

The backend port
================

.. automodule:: alphaDeesp.core.simulation
   :members: Simulation
   :member-order: bysource

.. automodule:: alphaDeesp.core.elements
   :members:

Orchestration
=============

.. automodule:: alphaDeesp.expert_operator
   :members:

.. autoclass:: alphaDeesp.core.alphadeesp.AlphaDeesp
   :members: run, get_ranked_combinations, compute_best_topologies,
             compute_all_combinations, rank_topologies, identify_routing_buses

.. autoclass:: alphaDeesp.core.alphadeesp.AlphaDeesp_warmStart

The graphs package
==================

Overflow model and renderer
---------------------------

.. autoclass:: alphaDeesp.core.graphs.overflow_graph.OverFlowGraph
   :members:

.. autoclass:: alphaDeesp.core.graphs.overflow_renderer.OverflowGraphRenderer
   :members:

Semantic edge roles
-------------------

.. automodule:: alphaDeesp.core.graphs.edge_roles
   :members:

Structured analysis
-------------------

.. autoclass:: alphaDeesp.core.graphs.power_flow_graph.PowerFlowGraph
   :members:

.. autoclass:: alphaDeesp.core.graphs.structured_overload_graph.Structured_Overload_Distribution_Graph
   :members:

.. autoclass:: alphaDeesp.core.graphs.constrained_path.ConstrainedPath
   :members:

Null-flow and consolidation mixins
----------------------------------

.. autoclass:: alphaDeesp.core.graphs.null_flow_graph.NullFlowGraphMixin
   :members: add_relevant_null_flow_lines, add_relevant_null_flow_lines_all_paths,
             detect_edges_to_keep

.. autoclass:: alphaDeesp.core.graphs.graph_consolidation.GraphConsolidationMixin
   :members: consolidate_graph, consolidate_constrained_path, consolidate_loop_path,
             reverse_edges

Graph helpers
-------------

.. automodule:: alphaDeesp.core.graphs.graph_utils
   :members:

.. automodule:: alphaDeesp.core.graphs.shortest_paths
   :members: shortest_path_min_weight_then_hops, shortest_path_mandatory_and_promoted,
             shortest_path_with_promoted_edges

.. automodule:: alphaDeesp.core.graphs.null_flow
   :members:

Interactive HTML viewer
=======================

.. autofunction:: alphaDeesp.core.interactive_html.build_interactive_html
