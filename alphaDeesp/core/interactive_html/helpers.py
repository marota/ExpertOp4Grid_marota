# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Pure helpers for the interactive viewer: title/colour parsing and
attribute normalisation. No graph or asset dependencies."""

from __future__ import annotations

import html as html_mod
from typing import Any, Dict, Optional, Tuple

from alphaDeesp.core.interactive_html.constants import _LAYER_LABELS


def _decode_title(text: str) -> str:
    """Graphviz HTML-escapes node/edge titles in SVG (``A&#45;&gt;B``)."""
    return html_mod.unescape(text or "")


def _split_edge_title(title: str) -> Tuple[str, str]:
    """Edge titles are ``"<src>->[<dst>"`` (digraph) or ``"<src>--<dst>"``."""
    title = _decode_title(title)
    for sep in ("->", "--"):
        if sep in title:
            src, dst = title.split(sep, 1)
            return src.strip(), dst.strip()
    return title, ""


def _color_to_layer_key(color: str) -> Optional[str]:
    """Map a (possibly compound or hex) color to a known layer key."""
    if not color:
        return None
    base = color.split(":", 1)[0].strip().strip('"').lower()
    if base in _LAYER_LABELS:
        return base
    return None


def _normalize_attrs(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Graphviz-internal _draw_/_ldraw_ keys and quoted strings."""
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        if k.startswith("_") or k in ("nodes", "edges", "objects", "subgraphs"):
            continue
        if isinstance(v, str):
            v = v.strip().strip('"')
        out[k] = v
    return out


def _is_truthy_flag(value: Any) -> bool:
    """Check whether a graph attribute represents a True boolean flag.

    Boolean attributes round-trip through pydot/graphviz/dot-json as
    string ``"True"``. We accept the native Python ``True`` for
    in-process callers and the string form for the JSON path.
    """
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False
