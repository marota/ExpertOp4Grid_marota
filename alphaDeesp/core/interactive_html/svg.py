# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Annotate the Graphviz SVG with stable ``data-*`` attributes and align
JSON edge ids with the SVG element ids."""

from __future__ import annotations

import html as html_mod
import re
from typing import Any, Dict, List, Tuple

from alphaDeesp.core.interactive_html.constants import _STYLE_LAYERS
from alphaDeesp.core.interactive_html.helpers import (
    _color_to_layer_key,
    _decode_title,
    _split_edge_title,
)


def _inject_svg_data_attrs(svg_bytes: bytes, model: Dict[str, Any]) -> str:
    """Annotate Graphviz SVG nodes/edges with stable data-* attributes.

    Graphviz emits ``<g id="nodeN" class="node"><title>NAME</title>``; we
    rely on the title to look up our model entries and append data-*
    attributes (which the JS uses for selectors and tooltips).
    """
    svg = svg_bytes.decode("utf-8")
    edge_by_id = {e["id"]: e for e in model["edges"]}
    node_by_name = {n["name"]: n for n in model["nodes"]}

    def _attrs_to_data(prefix: str, attrs: Dict[str, Any]) -> str:
        out: List[str] = []
        for k, v in attrs.items():
            safe_v = html_mod.escape(str(v), quote=True)
            out.append(f' data-{prefix}-{k}="{safe_v}"')
        return "".join(out)

    def _node_repl(match: re.Match) -> str:
        gid = match.group(1)
        title = match.group(2)
        name = _decode_title(title)
        node = node_by_name.get(name)
        if not node:
            return match.group(0)
        data = _attrs_to_data("attr", node["attrs"])
        return (
            f'<g id="{gid}" class="node" data-name="{html_mod.escape(name, quote=True)}"'
            f'{data}><title>{title}</title>'
        )

    def _edge_repl(match: re.Match) -> str:
        gid = match.group(1)
        title = match.group(2)
        edge = edge_by_id.get(gid)
        if not edge:
            return match.group(0)
        src, dst = edge["source"], edge["target"]
        layers: List[str] = []
        color_key = _color_to_layer_key(edge["attrs"].get("color", ""))
        if color_key:
            layers.append(f"color:{color_key}")
        style = (edge["attrs"].get("style") or "").lower()
        if style in _STYLE_LAYERS:
            layers.append(f"style:{style}")
        data = _attrs_to_data("attr", edge["attrs"])
        layer_attr = f' data-layers="{html_mod.escape(" ".join(layers), quote=True)}"' if layers else ""
        return (
            f'<g id="{gid}" class="edge"'
            f' data-source="{html_mod.escape(src, quote=True)}"'
            f' data-target="{html_mod.escape(dst, quote=True)}"'
            f'{layer_attr}{data}><title>{title}</title>'
        )

    svg = re.sub(
        r'<g id="(node\d+)" class="node">\s*<title>([^<]*)</title>',
        _node_repl,
        svg,
    )
    svg = re.sub(
        r'<g id="(edge\d+)" class="edge">\s*<title>([^<]*)</title>',
        _edge_repl,
        svg,
    )
    return svg


def _align_edge_ids_with_svg(svg_bytes: bytes, model: Dict[str, Any]) -> Dict[str, Any]:
    """Re-key edges in ``model`` so their ``id`` field matches the SVG's
    ``<g id="edgeN" class="edge">`` for the SAME (src, dst) endpoints.

    Background
    ----------
    Graphviz emits edge IDs ``edgeN`` in **two independent orderings** for
    the SVG and the JSON outputs of the same graph. ``_model_from_dot_json``
    assigns IDs by JSON-edge index but the SVG element with the same
    ``edgeN`` id often refers to a different edge (different (src, dst)
    pair). The downstream JS dim layer queries SVG elements **by id** —
    so a mismatch makes the wrong edges dim/highlight when a layer
    toggle is flipped (this is exactly the user-reported confusion
    SSV.OP7→GROSNP7 ↔ SSV.OP7→CREYSP7 / CHALOP6→CPVANP6 ↔
    CHALOP6→CHALOP3 in the small-grid scenario).

    Fix
    ---
    Walk the SVG, parse each edge's ``<title>`` to extract its true
    (src, dst), and greedily pair it with a JSON-side edge of matching
    endpoints. Each JSON edge is consumed at most once (parallel edges
    are paired in their relative order, which is stable across SVG and
    JSON). The model's edge IDs are updated in place; adjacency and
    layer membership lists are remapped through the same dict.

    Returns the updated model.
    """
    svg = svg_bytes.decode("utf-8")
    # Walk SVG edges in document order: ``<g id="edgeN" class="edge">
    # <title>SRC->DST</title>``. Graphviz HTML-escapes the title.
    pattern = re.compile(
        r'<g id="(edge\d+)" class="edge">\s*<title>([^<]*)</title>'
    )
    svg_edges_in_order: List[Tuple[str, str, str]] = []
    for m in pattern.finditer(svg):
        gid = m.group(1)
        src, dst = _split_edge_title(m.group(2))
        svg_edges_in_order.append((gid, src, dst))

    # Build a per-(src, dst) FIFO of JSON edges keeping their original order.
    json_edges = model["edges"]
    by_pair: Dict[Tuple[str, str], List[int]] = {}
    for i, e in enumerate(json_edges):
        by_pair.setdefault((e["source"], e["target"]), []).append(i)

    # Greedily match each SVG edge to the next un-consumed JSON edge of the
    # same endpoints. The remap dict translates "old (JSON-order) id" → "new
    # (SVG-order) id".
    remap: Dict[str, str] = {}
    for svg_id, s, t in svg_edges_in_order:
        candidates = by_pair.get((s, t)) or by_pair.get((t, s))
        if not candidates:
            continue
        json_idx = candidates.pop(0)
        old_id = json_edges[json_idx]["id"]
        if old_id == svg_id:
            continue
        remap[old_id] = svg_id

    if not remap:
        return model

    # Apply the remap. ``remap`` may contain swaps (a→b and b→a). To avoid
    # collisions we materialise the new IDs through a fresh dict in two
    # passes: first relabel each JSON edge to its SVG-aligned id, then walk
    # adjacency / layers to substitute the references.
    edge_id_lookup = {e["id"]: e for e in json_edges}
    for old_id, new_id in remap.items():
        edge = edge_id_lookup[old_id]
        edge["id"] = new_id

    # Adjacency entries reference edge ids by string — apply the same
    # substitution there.
    for entries in model.get("adjacency", {}).values():
        for entry in entries:
            if entry.get("edge") in remap:
                entry["edge"] = remap[entry["edge"]]

    # Layer membership lists use the same string ids.
    for layer in model.get("layers", []):
        layer["edges"] = [remap.get(eid, eid) for eid in layer.get("edges", [])]

    return model
