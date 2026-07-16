"""Semantic edge roles for overflow graphs.

The overflow *model* (:class:`~alphaDeesp.core.graphs.overflow_graph.OverFlowGraph`)
encodes each edge's role as a **base colour**. This module is the single
authority that maps that base colour to a stable semantic *role* — so
consumers (this package, the interactive viewer, downstream repos) never have
to parse Graphviz ``color`` strings, including the compound
``"colour:yellow:colour"`` highlight form produced by the renderer.

The model stays authoritative: the renderer *derives* the displayed colour
from the role/base colour, and when it wraps a base colour into a compound
highlight string it records the untouched base under the ``base_color`` edge
attribute. :func:`base_color_of` therefore prefers ``base_color`` and only
falls back to (compound-safe) parsing of ``color`` for graphs produced by
older code or another repository.
"""

from typing import Any, Dict

# Semantic roles — stable identifiers, independent of the rendered colour.
EDGE_ROLE_OVERLOAD = "overload"                              # base colour black
EDGE_ROLE_NEGATIVE = "negative"                             # base colour blue
EDGE_ROLE_POSITIVE = "positive"                             # base colour coral
EDGE_ROLE_INSIGNIFICANT = "insignificant"                  # base colour gray
EDGE_ROLE_NULL_NON_RECONNECTABLE = "null_non_reconnectable"  # base colour dimgray
EDGE_ROLE_UNKNOWN = "unknown"

_BASE_COLOR_TO_ROLE: Dict[str, str] = {
    "black": EDGE_ROLE_OVERLOAD,
    "blue": EDGE_ROLE_NEGATIVE,
    "coral": EDGE_ROLE_POSITIVE,
    "gray": EDGE_ROLE_INSIGNIFICANT,
    "grey": EDGE_ROLE_INSIGNIFICANT,
    "dimgray": EDGE_ROLE_NULL_NON_RECONNECTABLE,
    "dimgrey": EDGE_ROLE_NULL_NON_RECONNECTABLE,
}


def base_color_of(edge_data: Dict[str, Any]) -> str:
    """Return an edge's authoritative base colour (lower-cased).

    Prefers the stable ``base_color`` attribute; otherwise falls back to the
    ``color`` attribute, stripping any compound ``"c:yellow:c"`` wrapper. Returns
    ``""`` when neither is a usable string.
    """
    colour = edge_data.get("base_color") or edge_data.get("color", "")
    if not isinstance(colour, str):
        return ""
    # Compound Graphviz colours look like '"black:yellow:black"'.
    return colour.split(":", 1)[0].strip().strip('"').lower()


def edge_role_of(edge_data: Dict[str, Any]) -> str:
    """Return the semantic role of an edge from its authoritative base colour.

    :param edge_data: a NetworkX edge attribute dict (e.g. ``g.edges[u, v, k]``).
    :returns: one of the ``EDGE_ROLE_*`` constants (``EDGE_ROLE_UNKNOWN`` if the
        base colour is unrecognised).
    """
    return _BASE_COLOR_TO_ROLE.get(base_color_of(edge_data), EDGE_ROLE_UNKNOWN)
