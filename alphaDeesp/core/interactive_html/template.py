# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

"""Load the externalised viewer assets (CSS / JS / HTML skeleton) and
reconstitute the self-contained HTML template."""

from functools import lru_cache
from pathlib import Path

_ASSETS = Path(__file__).parent / "assets"


@lru_cache(maxsize=1)
def html_template() -> str:
    """Self-contained HTML template with ``__TITLE__`` / ``__SVG__`` /
    ``__MODEL_JSON__`` placeholders, reconstituted from the externalised
    ``viewer.css`` and ``viewer.js`` assets."""
    template = (_ASSETS / "template.html").read_text(encoding="utf-8")
    css = (_ASSETS / "viewer.css").read_text(encoding="utf-8")
    js = (_ASSETS / "viewer.js").read_text(encoding="utf-8")
    return template.replace("__CSS__", css).replace("__JS__", js)
