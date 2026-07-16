# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Layer-index construction: group edges/nodes by colour, style and
semantic flag so the viewer can offer toggles."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from alphaDeesp.core.interactive_html.constants import (
    _LAYER_LABELS,
    _LAYER_SECTIONS,
    _PROD_LOAD_VALUE_FLOOR_MW,
    _SECTION_ORDER,
    _SEMANTIC_LAYERS,
    _STYLE_LAYERS,
    _VALUE_NODE_LAYERS,
)
from alphaDeesp.core.interactive_html.helpers import (
    _color_to_layer_key,
    _is_truthy_flag,
)


def _build_layer_index(
    edges: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    """Group edges & nodes by colour / style / semantic flag so the UI
    can offer toggles. Each layer carries both ``nodes`` and ``edges``
    id lists (either may be empty).
    """
    by_color: Dict[str, List[str]] = {}
    by_style: Dict[str, List[str]] = {}
    edge_id_lookup = {e["id"]: e for e in edges}
    for e in edges:
        color_key = _color_to_layer_key(e["attrs"].get("color", ""))
        if color_key:
            by_color.setdefault(color_key, []).append(e["id"])
        style = (e["attrs"].get("style") or "").lower()
        if style in _STYLE_LAYERS:
            by_style.setdefault(style, []).append(e["id"])

    # Semantic flags scanned on both nodes and edges. Only emit a layer
    # entry if at least one element carries the flag — otherwise the
    # checkbox would be useless and noise.
    semantic_buckets: Dict[str, Dict[str, List[str]]] = {
        cfg["key"]: {"nodes": [], "edges": []} for cfg in _SEMANTIC_LAYERS
    }
    if nodes:
        for n in nodes:
            for cfg in _SEMANTIC_LAYERS:
                if cfg["scope"] in ("node", "both") and _is_truthy_flag(
                    n["attrs"].get(cfg["key"])
                ):
                    semantic_buckets[cfg["key"]]["nodes"].append(n["name"])
    for e in edges:
        for cfg in _SEMANTIC_LAYERS:
            if cfg["scope"] in ("edge", "both") and _is_truthy_flag(
                e["attrs"].get(cfg["key"])
            ):
                semantic_buckets[cfg["key"]]["edges"].append(e["id"])

    # For each colour / style layer, the endpoint nodes of every
    # claimed edge are also added to the layer so toggling, e.g.,
    # "Positive overflow" alone keeps the substations the coral edges
    # connect visible (the operator can still read the topology around
    # the highlighted edges instead of seeing them float in dimmed
    # space). We dedupe while preserving first-seen order.
    edge_id_to_endpoints: Dict[str, Tuple[str, str]] = {
        e["id"]: (e["source"], e["target"]) for e in edges
    }

    def _endpoint_nodes(edge_ids: List[str]) -> List[str]:
        seen: Dict[str, None] = {}
        for eid in edge_ids:
            ends = edge_id_to_endpoints.get(eid)
            if not ends:
                continue
            for n in ends:
                if n not in seen:
                    seen[n] = None
        return list(seen.keys())

    # Edge-only semantic layers (Overloads, Low margin lines) carry
    # their edges' endpoints too — same UX rationale as colour/style
    # layers: when the operator ticks "Overloads" alone the affected
    # substations stay visible.
    _EDGE_ONLY_SEMANTIC_KEYS = {
        cfg["key"] for cfg in _SEMANTIC_LAYERS if cfg["scope"] == "edge"
    }

    def _merge_dedup(base: List[str], extra: List[str]) -> List[str]:
        seen: Dict[str, None] = {n: None for n in base}
        for n in extra:
            if n not in seen:
                seen[n] = None
        return list(seen.keys())

    raw_layers: List[Dict[str, Any]] = []
    for key, ids in by_color.items():
        raw_layers.append({
            "key": f"color:{key}",
            "label": _LAYER_LABELS[key],
            "swatch": key,
            "nodes": _endpoint_nodes(ids),
            "edges": ids,
        })
    for key, ids in by_style.items():
        raw_layers.append({
            "key": f"style:{key}",
            "label": _STYLE_LAYERS[key],
            "swatch": "",
            "nodes": _endpoint_nodes(ids),
            "edges": ids,
        })
    for cfg in _SEMANTIC_LAYERS:
        bucket = semantic_buckets[cfg["key"]]
        if not bucket["nodes"] and not bucket["edges"]:
            continue
        nodes_for_layer = bucket["nodes"]
        if cfg["key"] in _EDGE_ONLY_SEMANTIC_KEYS:
            nodes_for_layer = _merge_dedup(
                nodes_for_layer, _endpoint_nodes(bucket["edges"])
            )
        raw_layers.append({
            "key": f"semantic:{cfg['key']}",
            "label": cfg["label"],
            "swatch": cfg["swatch"],
            "nodes": nodes_for_layer,
            "edges": bucket["edges"],
        })

    # Value-based node layers (Production / Consumption). Built from
    # the ``prod_or_load`` attribute upstream tagged on every node by
    # ``build_nodes`` — see _VALUE_NODE_LAYERS. The white-coloured
    # zero-balance nodes carry ``prod_or_load="load"`` AND
    # ``value="0.0"`` upstream by convention; the 1 MW floor filters
    # them out so the operator's "Consumption nodes" toggle doesn't
    # also tag every passive substation.
    if nodes:
        value_buckets: Dict[str, List[str]] = {
            cfg["key"]: [] for cfg in _VALUE_NODE_LAYERS
        }
        for n in nodes:
            kind = n["attrs"].get("prod_or_load")
            if kind not in value_buckets:
                continue
            try:
                magnitude = abs(float(n["attrs"].get("value", "0")))
            except (TypeError, ValueError):
                continue
            if magnitude < _PROD_LOAD_VALUE_FLOOR_MW:
                continue
            value_buckets[kind].append(n["name"])
        for cfg in _VALUE_NODE_LAYERS:
            ids = value_buckets[cfg["key"]]
            if not ids:
                continue
            raw_layers.append({
                "key": f"node:{cfg['key']}",
                "label": cfg["label"],
                "swatch": cfg["swatch"],
                "nodes": ids,
                "edges": [],
            })

    # Drop layers without a section assignment (e.g. ``color:black``,
    # ``color:gray``, ``color:darkred`` — historically redundant
    # buckets). Then group by section in the canonical order so the
    # JS can render them with section headers.
    sectioned: Dict[str, List[Dict[str, Any]]] = {s: [] for s in _SECTION_ORDER}
    for layer in raw_layers:
        section = _LAYER_SECTIONS.get(layer["key"])
        if section is None:
            continue
        layer["section"] = section
        sectioned.setdefault(section, []).append(layer)

    layers: List[Dict[str, Any]] = []
    for section in _SECTION_ORDER:
        layers.extend(sectioned.get(section, []))
    # Silence unused-var warning; lookup retained for future hover xref.
    del edge_id_lookup
    return layers
