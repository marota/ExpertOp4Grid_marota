# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Parse ``dot -Tjson`` into a flat node/edge model + adjacency map."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from alphaDeesp.core.interactive_html.helpers import _normalize_attrs
from alphaDeesp.core.interactive_html.layers import _build_layer_index


def _model_from_dot_json(dot_json: bytes) -> Dict[str, Any]:
    """Parse ``dot -Tjson`` into a flat node/edge model + adjacency map."""
    data = json.loads(dot_json.decode("utf-8"))
    objects: List[Dict[str, Any]] = data.get("objects", [])
    raw_edges: List[Dict[str, Any]] = data.get("edges", [])

    nodes: List[Dict[str, Any]] = []
    name_by_gvid: Dict[int, str] = {}
    for i, obj in enumerate(objects):
        if "nodes" in obj or "subgraphs" in obj:
            # cluster/subgraph entry — skip in v1
            continue
        name = obj.get("name", f"node{i}")
        name_by_gvid[obj.get("_gvid", i)] = name
        nodes.append({
            "name": name,
            "attrs": _normalize_attrs(obj),
        })

    edges: List[Dict[str, Any]] = []
    adjacency: Dict[str, List[Dict[str, str]]] = {n["name"]: [] for n in nodes}
    for j, edge in enumerate(raw_edges):
        src = name_by_gvid.get(edge.get("tail"))
        dst = name_by_gvid.get(edge.get("head"))
        if src is None or dst is None:
            continue
        attrs = _normalize_attrs(edge)
        edges.append({
            "id": f"edge{j + 1}",  # matches Graphviz SVG id naming
            "source": src,
            "target": dst,
            "attrs": attrs,
        })
        adjacency.setdefault(src, []).append({"node": dst, "edge": f"edge{j + 1}"})
        adjacency.setdefault(dst, []).append({"node": src, "edge": f"edge{j + 1}"})

    layers = _build_layer_index(edges, nodes)
    return {
        "nodes": nodes,
        "edges": edges,
        "adjacency": adjacency,
        "layers": layers,
    }
