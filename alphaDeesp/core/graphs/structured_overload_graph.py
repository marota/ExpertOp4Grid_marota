"""Structured_Overload_Distribution_Graph: extract constrained path,
loop paths and hubs from a raw overflow graph.
"""

import logging
from functools import cached_property
from typing import Any, List, Optional, Tuple

import networkx as nx
import pandas as pd
import rustworkx as rx

from alphaDeesp.core.graphs.constrained_path import ConstrainedPath
from alphaDeesp.core.graphs.graph_utils import delete_color_edges
from alphaDeesp.core.graphs.null_flow import (
    add_double_edges_null_redispatch,
    remove_unused_added_double_edge,
)

logger = logging.getLogger(__name__)

# Optional bound on the number of *nodes* in a loop path enumerated by
# :meth:`find_loops` (rustworkx ``cutoff`` counts nodes). Enumerating all
# simple paths between every pair of candidate hubs is combinatorial and can
# hang on very large grids. The bound is **OFF by default** (``None`` ==
# unbounded == the original behaviour): a too-small cutoff silently drops
# legitimate long loops — real RTE zone grids have loop paths well beyond 10
# nodes, and an emptied ``find_loops`` then breaks downstream consumers. Pass
# an int to opt into a bound only on grids where enumeration is a problem.
DEFAULT_LOOP_PATH_CUTOFF = None


class Structured_Overload_Distribution_Graph:
    """
    Staring from a raw overload distribution graph with color edges, this class identifies the underlying path structure in terms of constrained path, loop paths and hub nodes
    """
    def __init__(
        self,
        g: nx.MultiDiGraph,
        possible_hubs: Optional[List[Any]] = None,
        loop_path_cutoff: Optional[int] = DEFAULT_LOOP_PATH_CUTOFF,
    ) -> None:
        """
        Parameters
        ----------

        g: :class:`nx:MultiDiGraph`
            a raw graph from OverflowGraph

        possible_hubs: list, optional
            a pre-computed subset of hub candidates (e.g. when consolidating a
            previously built overflow graph)

        loop_path_cutoff: int, optional
            optional maximum number of *nodes* in a loop path enumerated by
            :meth:`find_loops`. Defaults to :data:`DEFAULT_LOOP_PATH_CUTOFF`
            (``None`` == unbounded == the original behaviour). Pass an int only
            to bound enumeration on grids where it would otherwise hang; too
            small a value silently drops legitimate long loops.

        """
        self.g_init = g
        self.loop_path_cutoff = loop_path_cutoff
        # Snapshot the graph at construction. The colour-filtered views are lazy
        # (below) but MUST reflect the graph *as it was when this object was
        # built* — the historical eager ``__init__`` copied every view at
        # construction, so a later mutation of the caller's graph (e.g.
        # ``consolidate_graph`` removing the ignored lines from the shared
        # ``OverFlowGraph.g`` before it re-reads this object) did not leak into
        # the views. Deferring the copies to first access would read the mutated
        # graph instead; freezing a single snapshot here preserves the exact
        # snapshot semantics while keeping the views lazy. ``g_init`` itself stays
        # a live reference — ``get_constrained_edges_nodes`` reads names off it and
        # historically saw the live graph, so that alias is deliberately kept.
        self._g_snapshot = g.copy()
        # Caller-supplied hub seeds influence *loop enumeration* only (see the
        # ``red_loops`` property); the *detected* hubs are exposed via ``hubs`` /
        # ``get_hubs``. Historically this seed was stored in ``self.hubs`` until
        # ``find_hubs`` overwrote it — capturing it separately makes the lazy
        # properties order-independent while preserving that exact behaviour.
        self._possible_hubs = list(possible_hubs) if possible_hubs is not None else []
        self.type = ""

        # The colour-filtered views, red loops and hubs are lazy *cached
        # properties* (computed once on first access, then memoised): a consumer
        # that needs only a subset — or that never consolidates — does not pay
        # for the rest, and the consolidation loop's repeated rebuilds compute
        # only what each iteration touches. The constrained path is validated
        # eagerly: it is cheap and preserves the construction-time "is this a
        # valid overflow graph" check that callers relied on.
        self.constrained_path = self.find_constrained_path()

    # ------------------------------------------------------------------
    # Lazy colour-filtered views (pure functions of the construction-time
    # snapshot; cached). Each removes the *union* of the listed colours in a
    # single graph copy.
    # ------------------------------------------------------------------

    @cached_property
    def g_without_pos_edges(self) -> nx.MultiDiGraph:
        """Overflow graph without coral (positive / loop) edges."""
        return delete_color_edges(self._g_snapshot, "coral")

    @cached_property
    def g_only_blue_components(self) -> nx.MultiDiGraph:
        """Only the blue constrained-path components (drops coral / gray / dimgray).

        ``dimgray`` (non-reconnectable null-flow lines that we still visualise)
        is removed too: they are not an operational path in the structured path.
        """
        return delete_color_edges(self._g_snapshot, ("coral", "gray", "dimgray"))

    @cached_property
    def g_without_constrained_edge(self) -> nx.MultiDiGraph:
        """Overflow graph without the black (overloaded) edges."""
        return delete_color_edges(self._g_snapshot, "black")

    @cached_property
    def g_without_gray_and_c_edge(self) -> nx.MultiDiGraph:
        """Only the coloured redispatch edges (drops black / gray / dimgray)."""
        return delete_color_edges(self._g_snapshot, ("black", "gray", "dimgray"))

    @cached_property
    def g_only_red_components(self) -> nx.MultiDiGraph:
        """Only the coral (positive / loop) redispatch edges."""
        return delete_color_edges(self._g_snapshot, ("black", "gray", "dimgray", "blue"))

    @cached_property
    def red_loops(self) -> pd.DataFrame:
        """Parallel (loop) paths, enumerated with the caller-supplied seed hubs.

        Mirrors the historical eager ``self.red_loops = find_loops()`` which ran
        *before* hub detection — so it uses ``_possible_hubs`` (the seed), not the
        detected ``hubs``. The public :meth:`find_loops` re-enumerates with the
        detected hubs when called after construction (as consolidation does).
        """
        return self._find_loops(self._possible_hubs)

    @cached_property
    def hubs(self) -> List[Any]:
        """Detected hub nodes (memoised)."""
        return self.find_hubs()

    def get_amont_blue_edges(self, g: nx.MultiDiGraph, node: Any) -> List[Any]:
        """
        From a given node, get blue edges (with negative overflow redispatch) that are above this node

        Parameters
        ----------

        g: :class:`nx:MultiDiGraph`
            an overflow redispatch networkx graph

        node: int
            node of interest

        Returns
        ----------

        res: ``array`` int
            ordered list of edges

        """
        res = []
        for e in nx.edge_dfs(g, node, orientation="reverse"):
            if g.edges[(e[0], e[1],e[2])]["color"] == "blue":
                res.append((e[0], e[1],e[2]))
        return res

    def get_aval_blue_edges(self, g: nx.MultiDiGraph, node: Any) -> List[Any]:
        """
        From a given node, get blue edges (with negative overflow redispatch) that are after this node

        Parameters
        ----------

        g: :class:`nx:MultiDiGraph`
            an overflow redispatch networkx graph

        node: int
            node of interest

        Returns
        ----------

        res: ``array`` int
            ordered list of edges

        """
        res = []
        # print("debug AlphaDeesp get aval blue edges")
        # print(list(nx.edge_dfs(g, node, orientation="original")))
        for e in nx.edge_dfs(g, node, orientation="original"):
            if g.edges[(e[0], e[1],e[2])]["color"] == "blue":
                res.append((e[0], e[1],e[2]))
        return res


    def find_hubs(self) -> List[Any]:
        """
        "A hub (carrefour_electrique) has a constrained_path and positiv reports"

        Returns
        ----------

        res: list int
            a list of nodes that are detected as hubs
        """
        g = self.g_without_constrained_edge
        hubs = []

        # ``constrained_path`` is validated eagerly in ``__init__``, so it is
        # always available here.
        logger.debug("In find_hubs(): constrained_path = %s", self.constrained_path)

        # for nodes in aval, if node has RED inputs (ie incoming flows) then it is a hub
        for node in self.constrained_path.n_aval():
            in_edges = list(g.in_edges(node,keys=True))
            for e in in_edges:
                if g.edges[e]["color"] == "coral":
                    hubs.append(node)
                    break

        # for nodes in amont, if node has RED outputs (ie outgoing flows) then it is a hub
        for node in self.constrained_path.n_amont():
            out_edges = list(g.out_edges(node,keys=True))
            for e in out_edges:
                if g.edges[e]["color"] == "coral":
                    hubs.append(node)
                    break

        # print("get_hubs = ", hubs)
        return hubs

    def get_hubs(self) -> List[Any]:
        return self.hubs

    def find_loops(self) -> pd.DataFrame:
        """Enumerate loop paths using the *currently detected* hubs (``self.hubs``).

        The cached :attr:`red_loops` uses the caller-supplied seed hubs instead
        (see its docstring); consolidation re-enumerates through this method
        after the hubs have been detected.
        """
        return self._find_loops(self.hubs)

    def _find_loops(self, hubs: List[Any]) -> pd.DataFrame:

        """This function returns all parallel paths. After discussing with Antoine, start with the most "en Aval" node,
        and walk in reverse for loops and parallel path returns a dict with all data

        Returns
        ----------

        res: pd.DataFrame
            a dataframe with rows representing each detected path, with column attibutes "Source, Target, Path" with Path representing a list of nodes
        """

        attr_edge_direction=nx.get_edge_attributes(self.g_only_red_components, "dir")
        if len(attr_edge_direction)!=0:
            # add edges to make simple paths work for no direction edges
            edges_to_double, edges_double_added = add_double_edges_null_redispatch(self.g_only_red_components,color_init="coral",only_no_dir=True)

        # print("==================== In function get_loops ====================")
        g = self.g_only_red_components
        c_path_n = self.constrained_path.full_n_constrained_path()
        if len(hubs)!=0:#already some insights of possible hubs
            c_path_n=hubs

        # --- 1. PRE-PROCESSING (Rustworkx) ---
        # Convert NetworkX graph to Rustworkx for 50x speedup
        rx_graph = rx.networkx_converter(g)

        # Map Node Names (Strings) -> Node Indices (Integers)
        nodes_list = list(g.nodes())
        node_map = {node: i for i, node in enumerate(nodes_list)}

        all_loop_paths = []

        # --- 2. SEARCH LOOP ---
        # We iterate efficiently
        for i in range(len(c_path_n)):
            for j in range(len(c_path_n) - 1, i, -1):
                src_name = c_path_n[i]
                tgt_name = c_path_n[j]

                # Ensure nodes exist in the graph to avoid crashes
                if src_name in node_map and tgt_name in node_map:
                    s_idx = node_map[src_name]
                    t_idx = node_map[tgt_name]

                    # Rustworkx: Find all simple paths (FAST).
                    # ``cutoff`` (max nodes per path) is crucial to prevent
                    # hanging on large grids; see ``loop_path_cutoff``. rustworkx
                    # treats ``cutoff=None`` as "no bound".
                    paths_indices = rx.all_simple_paths(
                        rx_graph, s_idx, t_idx, min_depth=1, cutoff=self.loop_path_cutoff)

                    # Convert Indices -> Names
                    # We extend the main list directly
                    paths_names = [[nodes_list[idx] for idx in p] for p in paths_indices]
                    all_loop_paths.extend(paths_names)

        # --- 3. OPTIMIZED DATAFRAME CREATION ---
        # Instead of iterating and appending, we build lists directly.
        # This assumes 'all_loop_paths' is a list of lists: [['A', 'B'], ['C', 'D']]

        if not all_loop_paths:
            # Handle empty case to avoid errors
            data_for_df = {"Source": [], "Target": [], "Path": []}
        else:
            # List comprehensions are significantly faster than .append() loop
            data_for_df = {
                "Source": [p[0] for p in all_loop_paths],
                "Target": [p[-1] for p in all_loop_paths],
                "Path": all_loop_paths
            }

        # --- 4. GRAPH CLEANUP (Your original logic) ---
        if len(attr_edge_direction) != 0:
            # remove added edges that made simple paths working for no direction edges
            self.g_only_red_components = remove_unused_added_double_edge(
                self.g_only_red_components,
                set(edges_to_double.values()),
                edges_to_double,
                edges_double_added
            )

        return pd.DataFrame(data_for_df)

    def get_loops(self) -> pd.DataFrame:
        return self.red_loops

    def find_constrained_path(self) -> "ConstrainedPath":
        """Find and return the constrained path.

        Returns
        -------
        ConstrainedPath
            a constrained path object
        """
        constrained_edge = None
        edge_list = nx.get_edge_attributes(self.g_only_blue_components, "color")
        for edge, color in edge_list.items():
            if "black" in color:
                constrained_edge = edge
        amont_edges = self.get_amont_blue_edges(self.g_only_blue_components, constrained_edge[0])
        aval_edges = self.get_aval_blue_edges(self.g_only_blue_components, constrained_edge[1])

        return ConstrainedPath(amont_edges,constrained_edge,aval_edges)

    def get_constrained_path(self) -> "ConstrainedPath":
        return self.constrained_path

    def get_constrained_edges_nodes(self) -> Tuple[List[Any], List[Any], List[Any], List[Any]]:
        """Identify the constrained path within the distribution graph.

        Returns
        -------
        tuple
            ``(edges_constrained_path, nodes_constrained_path, other_blue_edges,
            other_blue_nodes)`` — the line names and nodes on the constrained
            path, plus the blue edges/nodes that are *not* on it.
        """
        constrained_path_object = self.constrained_path#self.find_constrained_path()
        nodes_constrained_path = constrained_path_object.full_n_constrained_path()
        edges_constrained_path = []

        edge_names = nx.get_edge_attributes(self.g_init, 'name')
        edges_constrained_path += [edge_name for edge, edge_name in edge_names.items() if
                                   edge in constrained_path_object.amont_edges]
        edges_constrained_path += [edge_name for edge, edge_name in edge_names.items() if
                                   edge in constrained_path_object.aval_edges]

        if type(constrained_path_object.constrained_edge) is list:
            edges_constrained_path += [edge_name for edge, edge_name in edge_names.items() if
                                       edge in constrained_path_object.constrained_edge]
        else:
            edges_constrained_path.append([edge_name for edge, edge_name in edge_names.items() if
                                           edge == constrained_path_object.constrained_edge][0])

        g_blue=self.g_only_blue_components.copy()
        g_blue.remove_edges_from(edges_constrained_path)

        other_blue_edges=list(g_blue.edges())
        other_blue_nodes=[node for node in g_blue.nodes() if node not in nodes_constrained_path]

        return list(set(edges_constrained_path)), nodes_constrained_path, other_blue_edges, other_blue_nodes

    def get_dispatch_edges_nodes(self, only_loop_paths: bool = True) -> Tuple[List[Any], List[Any]]:
        """Identify the dispatch (loop) path within the distribution graph.

        Parameters
        ----------
        only_loop_paths : bool
            when True (default) restrict to nodes that lie on a detected red-loop
            path; otherwise use every node of the red-component graph.

        Returns
        -------
        tuple
            ``(lines_redispatch, list_nodes_dispatch_path)`` — the line names and
            nodes that make up the dispatch path.
        """
        lines_redispatch=[]
        list_nodes_dispatch_path=[]
        g_red = self.g_only_red_components

        if only_loop_paths:
            # ``Series.sum()`` on an empty ``Path`` column returns the scalar
            # 0 (not an empty list), so guard the no-loop case explicitly to
            # avoid ``set(0)`` -> "int object is not iterable". ``sum(paths,
            # [])`` concatenates the per-loop node lists and yields [] when
            # there are no loops.
            paths = self.red_loops.Path
            list_nodes_dispatch_path = list(set(sum(paths, []))) if len(paths) else []
        else:
            list_nodes_dispatch_path=list(g_red.nodes)

        edge_names_red = nx.get_edge_attributes(g_red, 'name')
        lines_redispatch=[edge_name for edge, edge_name in edge_names_red.items() if
                                (edge[0] in list_nodes_dispatch_path) and (edge[1] in list_nodes_dispatch_path)]

        return lines_redispatch, list_nodes_dispatch_path
