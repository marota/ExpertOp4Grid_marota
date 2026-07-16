# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Assemble the interactive viewer HTML from a pydot graph."""

from __future__ import annotations

import html as html_mod
import json
from typing import Any

import pydot

from alphaDeesp.core.interactive_html.model import _model_from_dot_json
from alphaDeesp.core.interactive_html.svg import (
    _align_edge_ids_with_svg,
    _inject_svg_data_attrs,
)
from alphaDeesp.core.interactive_html.template import html_template


def build_interactive_html(
    pydot_graph: pydot.Graph,
    prog: Any = "dot",
    title: str = "ExpertOp4Grid — interactive overflow graph",
) -> str:
    """Render ``pydot_graph`` to interactive HTML.

    Returns the HTML string. Caller decides where to write it.
    """
    svg_bytes = pydot_graph.create(prog=prog, format="svg")
    json_bytes = pydot_graph.create(prog=prog, format="json")
    model = _model_from_dot_json(json_bytes)
    # Align JSON edge ids with the SVG element ids — graphviz emits the
    # two orderings independently and the downstream JS toggles SVG
    # elements by id, so a mismatch silently dims the wrong edges.
    model = _align_edge_ids_with_svg(svg_bytes, model)
    annotated_svg = _inject_svg_data_attrs(svg_bytes, model)
    return (
        html_template()
        .replace("__TITLE__", html_mod.escape(title))
        .replace("__SVG__", annotated_svg)
        .replace("__MODEL_JSON__", json.dumps(model))
    )
