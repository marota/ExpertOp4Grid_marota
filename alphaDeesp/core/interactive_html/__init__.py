# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Build an interactive HTML viewer around a Graphviz-rendered SVG.

The viewer keeps the exact dot-computed positions and bezier-curved edges
(it reuses the SVG produced by Graphviz verbatim) and layers JS-driven
interactions on top: pan/zoom, hover tooltip, click-to-highlight
neighborhood, search, layer toggles by edge color/style.

The companion JSON (``dot -Tjson`` flavour) is parsed in Python so the
embedded data structure exposed to the browser is a flat node/edge model
with a pre-computed adjacency map — interactions stay O(1) at runtime.

This package was split out of the former single ``interactive_html.py`` module;
the CSS/JS/HTML skeleton now live as externalised assets under ``assets/``.
The public surface (and the internal helpers referenced by tests) is
re-exported here so ``from alphaDeesp.core.interactive_html import ...``
keeps working unchanged."""

from alphaDeesp.core.interactive_html.helpers import (
    _color_to_layer_key,
    _decode_title,
    _is_truthy_flag,
    _normalize_attrs,
    _split_edge_title,
)
from alphaDeesp.core.interactive_html.layers import _build_layer_index
from alphaDeesp.core.interactive_html.model import _model_from_dot_json
from alphaDeesp.core.interactive_html.svg import (
    _align_edge_ids_with_svg,
    _inject_svg_data_attrs,
)
from alphaDeesp.core.interactive_html.render import build_interactive_html

# The public entry point plus the internal helpers that were importable from
# the former single module (kept for backwards compatibility and referenced by
# tests). Listing them in ``__all__`` also marks them as intentional re-exports
# for static analysers.
__all__ = [
    "build_interactive_html",
    "_build_layer_index",
    "_color_to_layer_key",
    "_decode_title",
    "_is_truthy_flag",
    "_normalize_attrs",
    "_split_edge_title",
    "_model_from_dot_json",
    "_align_edge_ids_with_svg",
    "_inject_svg_data_attrs",
]
