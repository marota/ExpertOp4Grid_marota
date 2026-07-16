"""Shortest-path helpers with mandatory / promoted-edge constraints.

These live here (rather than in :mod:`graph_utils`) because they encode
a specific optimisation strategy — minimise physical weight first, then
favour promoted edges, then minimise hop count.
"""

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import networkx as nx


def _make_incentivized_weight(
    G: Any,
    weight_attr: str,
    huge_multiplier: float,
    normal_hop_cost: float,
    promoted_hop_cost: float,
    promoted_set: Set[Any],
) -> Any:
    """Build a Dijkstra weight fn ``(physical_weight * huge) + hop_cost``.

    Physical weight dominates; ``hop_cost`` is ``promoted_hop_cost`` on a promoted
    edge, else ``normal_hop_cost`` — so among equal-weight paths the one using
    more promoted edges (then fewer hops) wins.

    Handles **both** graph kinds correctly. For a ``MultiDiGraph`` networkx
    passes the ``{key: attr}`` view of the parallel edges, so we take the minimum
    physical weight across them and treat the connection as promoted when either
    ``(u, v)`` or any ``(u, v, key)`` is in ``promoted_set``. For a plain graph
    the single attribute dict is used directly. (The historical closures called
    ``attr.get(weight_attr)`` unconditionally, which silently read ``0`` for
    every multigraph edge.)
    """
    is_multi = G.is_multigraph()

    def incentivized_weight(u: Any, v: Any, attr: Dict[Any, Any]) -> float:
        if is_multi:
            weights = [d.get(weight_attr, 0) for d in attr.values()]
            real_weight = min(weights) if weights else 0
            promoted = (u, v) in promoted_set or any(
                (u, v, key) in promoted_set for key in attr.keys())
        else:
            real_weight = attr.get(weight_attr, 0)
            promoted = (u, v) in promoted_set
        if real_weight < 0:
            raise ValueError("Dijkstra does not accept negative weights.")
        hop_cost = promoted_hop_cost if promoted else normal_hop_cost
        return (real_weight * huge_multiplier) + hop_cost

    return incentivized_weight


def shortest_path_min_weight_then_hops(G: Any, source: Any, target: Any, mandatory_edge: Tuple[Any, ...], weight_attr: str = "weight") -> Tuple[Optional[List[Any]], float]:
    """
    Finds the path that:
    1. Passes through 'mandatory_edge'
    2. Minimizes Total Weight (Primary)
    3. Minimizes Edge Count (Secondary/Tie-breaker)
    """
    # Large multiplier ensures Weight always dominates Hop Count.
    # Must be larger than the max possible number of edges in a path (e.g., number of nodes).
    MULTIPLIER = 1_000_000

    # Weight fn: (Actual_Weight * 1,000,000) + 1. No promotion here, so the hop
    # cost is a constant 1 (pure min-weight then min-hops).
    composite_weight = _make_incentivized_weight(
        G, weight_attr, MULTIPLIER,
        normal_hop_cost=1, promoted_hop_cost=1, promoted_set=set())

    # Unpack mandatory edge
    u, v = mandatory_edge[0], mandatory_edge[1]

    try:
        # 1. Path Source -> u (Using composite weight)
        path_S_to_u = nx.dijkstra_path(G, source, u, weight=composite_weight)

        # 2. Path v -> Target (Using composite weight)
        path_v_to_T = nx.dijkstra_path(G, v, target, weight=composite_weight)

        # 3. Handle the mandatory edge itself
        # We need to find the specific parallel key that minimizes (Weight, then Hops)
        # Usually, hops is always 1 for a single edge, so just min(weight)
        if G.is_multigraph():
            if len(mandatory_edge) == 3:
                # Key was specified explicitly
                key = mandatory_edge[2]
                mid_edge_attr = G[u][v][key]
            else:
                # Key not specified: Find the parallel edge with lowest weight
                # (All parallel edges are 1 hop, so just strictly minimize weight)
                mid_edge_attr = min(G[u][v].values(), key=lambda x: x.get(weight_attr, 0))
        else:
            mid_edge_attr = G[u][v]

        # Calculate real final stats (without the multiplier math)
        full_path = path_S_to_u + path_v_to_T

        # Calculate strict total weight (sum of original weights)
        # Note: We recalculate using path_weight to be precise
        cost_S_u = nx.path_weight(G, path_S_to_u, weight=weight_attr)
        cost_v_T = nx.path_weight(G, path_v_to_T, weight=weight_attr)
        mid_cost = mid_edge_attr.get(weight_attr, 0)

        total_real_weight = cost_S_u + mid_cost + cost_v_T

        return full_path, total_real_weight

    except nx.NetworkXNoPath:
        return None, float('inf')

def shortest_path_mandatory_and_promoted(G: Any, source: Any, target: Any, mandatory_edge: Tuple[Any, ...], promoted_edges: Iterable[Any], weight_attr: str = "weight") -> Tuple[Optional[List[Any]], float]:
    """
    Finds a path that:
    1. MUST pass through 'mandatory_edge'.
    2. Minimizes Total Physical Weight (Primary constraint).
    3. Maximizes use of 'promoted_edges' (Secondary preference).
    4. Minimizes Total Hops (Tertiary preference).

    Args:
        G: The graph (DiGraph or MultiDiGraph).
        source, target: Node IDs.
        mandatory_edge: Tuple (u, v) or (u, v, key).
        promoted_edges: List of edges to favor [(u, v), ...].
    """

    # --- Configuration ---
    # HUGE: Ensures physical weight dominates everything (1kg of extra weight is worse than 1M extra hops)
    HUGE_MULTIPLIER = 1_000_000_000

    # COST: The "Virtual Price" of crossing an edge
    # We prefer paying 1 dollar (Promoted) over 100 dollars (Normal)
    NORMAL_HOP_COST = 100
    PROMOTED_HOP_COST = 1

    # --- 1. Custom weight fn (multigraph-correct promoted matching) ---
    incentivized_weight = _make_incentivized_weight(
        G, weight_attr, HUGE_MULTIPLIER,
        normal_hop_cost=NORMAL_HOP_COST, promoted_hop_cost=PROMOTED_HOP_COST,
        promoted_set=set(promoted_edges))

    # --- 2. Decompose the Problem ---
    u_mand, v_mand = mandatory_edge[0], mandatory_edge[1]

    try:
        # Step A: Find best promoted path from Source -> Mandatory Start (u)
        path_S_to_u = nx.dijkstra_path(G, source, u_mand, weight=incentivized_weight)

        # Step B: Find best promoted path from Mandatory End (v) -> Target
        path_v_to_T = nx.dijkstra_path(G, v_mand, target, weight=incentivized_weight)

        # --- 3. Construct the Full Path ---
        # path_S_to_u ends with 'u', path_v_to_T starts with 'v'
        # We join them: [... , u] + [v, ...]
        full_path = path_S_to_u + path_v_to_T

        # --- 4. Calculate Real Stats (Optional but useful) ---
        # We recalculate the strict physical weight to return clean data
        cost_S_u = nx.path_weight(G, path_S_to_u, weight=weight_attr)
        cost_v_T = nx.path_weight(G, path_v_to_T, weight=weight_attr)

        # Handle the mandatory edge's own weight
        if G.is_multigraph():
            if len(mandatory_edge) == 3:
                key = mandatory_edge[2]
                mand_cost = G[u_mand][v_mand][key].get(weight_attr, 0)
            else:
                # If key not specified, assume the cheapest parallel line
                mand_cost = min(d.get(weight_attr, 0) for d in G[u_mand][v_mand].values())
        else:
            mand_cost = G[u_mand][v_mand].get(weight_attr, 0)

        total_real_weight = cost_S_u + mand_cost + cost_v_T

        return full_path, total_real_weight

    except nx.NetworkXNoPath:
        return None, float('inf')

def shortest_path_with_promoted_edges(G: Any, source: Any, target: Any, promoted_edges: Iterable[Any], weight_attr: str = "weight") -> Tuple[Optional[List[Any]], float]:
    """
    Finds a path from source to target that:
    1. Minimizes Total Weight (Primary - strict dominance)
    2. Maximizes use of 'promoted_edges' (Secondary)
    3. Minimizes Total Hops (Tertiary)

    Args:
        G: The graph.
        source, target: Node IDs.
        promoted_edges: A list of edges to favor. Can be tuples (u, v) or (u, v, key).
        weight_attr: The physical weight attribute name.
    """

    # Configuration
    # HUGE: Ensures physical weight always dominates preference.
    # PENALTY: How much we dislike normal edges.
    #          100 means: "We prefer 3 promoted edges over 1 normal edge."
    HUGE_MULTIPLIER = 1_000_000_000
    NORMAL_HOP_COST = 100
    PROMOTED_HOP_COST = 33

    # 1. Weight fn: multigraph-correct, matches promoted (u,v) or (u,v,key).
    incentivized_weight = _make_incentivized_weight(
        G, weight_attr, HUGE_MULTIPLIER,
        normal_hop_cost=NORMAL_HOP_COST, promoted_hop_cost=PROMOTED_HOP_COST,
        promoted_set=set(promoted_edges))

    # 3. Run Dijkstra with the Custom Weight
    try:
        path = nx.dijkstra_path(G, source, target, weight=incentivized_weight)

        # 4. Calculate Real Metrics (for display/return)
        total_weight = nx.path_weight(G, path, weight=weight_attr)
        return path, total_weight

    except nx.NetworkXNoPath:
        return None, float('inf')
