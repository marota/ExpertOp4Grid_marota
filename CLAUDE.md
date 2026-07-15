# CLAUDE.md

This file gives Claude Code (claude.ai/code) working context for this repository.

## Project Overview

**ExpertOp4Grid** (package: `alphaDeesp`) is a Python expert system that solves
power-line overloads on an electrical grid using non-linear topological actions
(bus-bar splits, line switching). Given an overloaded line, it builds an
"influence graph" around the overload, ranks candidate substations/topologies,
simulates the top-ranked ones, and returns a score (0–4) indicating how well
each remediation fixes the overload.

It is the implementation of the paper *"Expert system for topological action
discovery in smart grids"*
(https://hal.archives-ouvertes.fr/hal-01897931/).

## Repository Layout

```
alphaDeesp/
├── main.py                         # CLI entry point (`expertop4grid`)
├── expert_operator.py              # Orchestrator: simulator -> AlphaDeesp -> results
├── Expert_rule_action_verification.py  # Rule-checking utilities for proposed actions
├── core/
│   ├── alphadeesp.py               # AlphaDeesp algorithm (ranking, topology exploration)
│   ├── topology_scorer.py          # TopologyScorerMixin (score helpers for AlphaDeesp)
│   ├── topo_applicator.py          # TopoApplicatorMixin (apply topo vectors to the graph)
│   ├── twin_nodes.py               # Twin-node id scheme (busbar-split node encoding)
│   ├── graphsAndPaths.py           # Back-compat shim → re-exports from core/graphs/
│   ├── graphs/                     # Graph layer (split out of the old graphsAndPaths.py)
│   │   ├── overflow_graph.py       # OverFlowGraph — the overflow *semantic model*
│   │   ├── overflow_renderer.py    # OverflowGraphRenderer — Graphviz *presentation* only
│   │   ├── power_flow_graph.py     # PowerFlowGraph (base current-state graph)
│   │   ├── structured_overload_graph.py  # Structured_Overload_Distribution_Graph
│   │   ├── constrained_path.py     # ConstrainedPath value object
│   │   ├── null_flow_graph.py      # NullFlowGraphMixin (null-flow line handling)
│   │   ├── null_flow.py            # double/un-double null-flow edge helpers
│   │   ├── graph_consolidation.py  # GraphConsolidationMixin (disambiguation)
│   │   ├── graph_utils.py          # pure networkx helpers (delete_color_edges, ...)
│   │   ├── shortest_paths.py       # mandatory/promoted-edge shortest paths
│   │   └── constants.py            # default_voltage_colors, ...
│   ├── interactive_html.py         # Interactive HTML/SVG overflow viewer (used by other repos)
│   ├── simulation.py               # Abstract Simulation base class + DataFrame plumbing
│   ├── network.py                  # Network / Substation model objects
│   ├── elements.py                 # Production, Consumption, OriginLine, ExtremityLine classes
│   ├── printer.py                  # Graphviz/shell printing helpers
│   ├── grid2op/                    # Grid2op backend (Grid2opSimulation, Grid2opObservationLoader)
│   └── pypownet/                   # Pypownet backend (legacy / deprecated)
├── ressources/
│   ├── config/config.ini           # Default runtime config (thresholds, layout, simulator type)
│   └── parameters/                 # Built-in grids (l2rpn_2019, rte_case14_realistic, custom14, ...)
└── tests/                          # pytest suite (unit + integration, grid2op + pypownet)
docs/                               # Sphinx sources (RST) + CODE_REVIEW.md
scripts/code_quality_report.py      # Aggregated radon/vulture/ruff/interrogate report
getting_started/                    # Jupyter tutorial notebooks
.circleci/config.yml                # CI: pytest on cimg/python:3.12 with graphviz
```

## Architecture

```
                       ┌────────────────────┐
   config.ini + CLI -> │ alphaDeesp.main    │
                       └────────┬───────────┘
                                │ builds
                                ▼
              ┌────────────────────────────────────┐
              │ Grid2opSimulation / PypownetSimu.  │  (subclass of core.simulation.Simulation)
              └────────┬───────────────────────────┘
                       │ provides topology, dataframe, mappings
                       ▼
              ┌────────────────────────────────────┐
              │ expert_operator.expert_operator()  │
              └────────┬───────────────────────────┘
                       │
                       ├─► OverFlowGraph (core/graphs/overflow_graph.py)
                       ├─► AlphaDeesp.get_ranked_combinations()
                       └─► sim.compute_new_network_changes() -> end-result DataFrame
```

Key contract: any new simulator backend must implement the abstract methods of
`alphaDeesp/core/simulation.py::Simulation` (get_dataframe, isAntenna,
get_substation_elements, compute_new_network_changes, etc.).

### The `graphs/` package (and `OverFlowGraph`)

`core/graphsAndPaths.py` is now a **backwards-compatible shim** that re-exports
the public surface of the `core/graphs/` package. External code (and other
repos) can keep importing `from alphaDeesp.core.graphsAndPaths import
OverFlowGraph, ...`; new code should import from `alphaDeesp.core.graphs`.

`OverFlowGraph` is split into a **semantic model** and a **renderer**:

- `graphs/overflow_graph.py::OverFlowGraph` owns the semantic model — graph
  topology, per-edge redispatch magnitude, edge *role* encoded as a base
  colour (`black` overload / `blue` negative / `coral` positive / `gray`
  insignificant), and the boolean semantic flags consumed downstream
  (`is_overload`, `is_monitored`, `on_constrained_path`, `in_red_loop`,
  `is_hub`, `is_extra_cut`). The public method signatures are unchanged.
- `graphs/overflow_renderer.py::OverflowGraphRenderer` owns all Graphviz
  *presentation* (penwidth scaling, node shapes, tapered swap styling, the
  compound `"colour:yellow:colour"` highlight strings and HTML loading
  labels, and plotting). It is **stateless** (static methods over a passed-in
  graph) so downstream repos can reuse it on any compatible `MultiDiGraph`.

The public surface of the package is pinned by `tests/test_graphs_package.py`
(`EXPECTED_PUBLIC_NAMES` / `EXPECTED_SUBMODULES`) — update those sets when you
add or move a public symbol.

## Common Commands

```bash
# Install (editable is fine; entry point `expertop4grid` is registered)
pip install -e .

# Run in manual mode on a built-in grid (cut line 9, timestep 0, scenario 0)
python -m alphaDeesp.main -l 9 -s 0 -c 0 -t 0
# or via the installed console script
expertop4grid -l 9 -s 0 -c 0 -t 0

# Flags:
#   -l/--ltc             lines to cut (single int for now)
#   -s/--snapshot        0|1 — render graphs to output/
#   -c/--chronicscenario chronic scenario id/name (default 0)
#   -t/--timestep        starting timestep (default 0)
#   -f/--fileconfig      alternate config.ini path
#   -d/--debug           0|1

# Run tests (CircleCI command, skipping pypownet + CLI + expert-rules suites)
pytest --ignore=alphaDeesp/tests/pypownet/ \
       --ignore=alphaDeesp/tests/test_cli.py \
       --ignore=alphaDeesp/tests/test_expert_rules.py

# CLI smoke test (runs separately in CI)
pytest alphaDeesp/tests/test_cli.py

# Full test suite with warning suppression (from README)
pytest --verbose --continue-on-collection-errors -p no:warnings
```

## Configuration (config.ini)

Defaults live in `alphaDeesp/ressources/config/config.ini`. Important keys:

- `simulatorType` — `Grid2OP` | `Pypownet` | `RTE`
- `gridPath` — folder containing the grid (defaults to packaged `l2rpn_2019`)
- `outputPath` — where snapshot plots are written
- `ThresholdReportOfLine`, `ThersholdMinPowerOfLoop`, `ratioToKeepLoop`,
  `ratioToReconsiderFlowDirection`, `maxUnusedLines`,
  `totalNumberOfSimulatedTopos`, `numberOfSimulatedToposPerNode` — tunables for
  the AlphaDeesp ranking and simulation step.

All of these can alternatively be supplied as a Python dict to the
`expert_operator()` API when embedding the system in another agent.

## Dependencies

Runtime: `Grid2Op`, `lightsim2grid`, `networkx`, `rustworkx`, `pandapower`,
`pandas`, `numpy`, `scipy`, `matplotlib`, `graphviz`, `pydot`, `Sphinx`,
`pytest`.

Optional: `pypownet>=2.2.0`, `oct2py`, `pypower` (for the legacy backend).

Python: `setup.py` declares `python_requires=">=3.9"` with classifiers for
3.9–3.12; CI runs on 3.12. Note the `graphs/` package unit tests
(`test_overflow_graph.py`, `test_graphs_package.py`, `test_null_flow.py`, ...)
run **without** grid2op; the grid2op integration suites, `alphadeesp_test.py`,
`test_cli.py` and `test_expert_rules.py` require `grid2op` + `lightsim2grid`
installed.

Graphviz **executables** must be on PATH for snapshot/plot mode (not just the
Python binding). On Debian/Ubuntu: `apt-get install graphviz`.

## Conventions and Gotchas

- The package directory is spelled **`alphaDeesp`** (lowercase-a) even though
  the PyPI name is `ExpertOp4Grid`. Imports use `from alphaDeesp.core...`.
- The `ressources/` directory keeps the French spelling — do not rename it; it
  is referenced by config paths and tests.
- `simulatorType = Grid2OP` (exact casing) in config.ini; `Pypownet` and `RTE`
  are alternative literals checked in `main.py`.
- Naming is mixed: public API uses both `snake_case` (`get_dataframe`) and
  `camelCase` (`isAntenna`, `isDoubleLine`, `getLinesAtSubAndBusbar`), plus the
  PascalCase-with-underscores `Structured_Overload_Distribution_Graph`.
  Preserve existing names when editing to avoid breaking the abstract contract
  and external importers.
- `core/elements.py` classes are now imported **explicitly** (e.g.
  `from alphaDeesp.core.elements import Consumption, Production`); the old
  `from elements import *` star imports have been removed.
- Logging: newer modules (`graphs/`, `alphadeesp.py`, `simulation.py`,
  `elements.py`, `main.py`) use the `logging` framework; the older backends
  (`grid2op/`, `pypownet/`, `network.py`, `printer.py`) still `print()` in
  places. Prefer `logging` in new/edited code.
- Typing: the `graphs/` package, `simulation.py`, `elements.py`, `network.py`
  and `alphadeesp.py` carry type annotations. CI enforces mypy **strictly** on
  `simulation.py` and `elements.py` (permissive elsewhere). Do not reintroduce
  the "codebase is untyped" assumption.
- `graphs/graph_utils.delete_color_edges` accepts a single colour **or an
  iterable of colours** and removes them in one graph copy — prefer the
  multi-colour form to avoid chained full-graph copies.
- `Structured_Overload_Distribution_Graph.find_loops` bounds simple-path
  enumeration with `loop_path_cutoff` (default 10 nodes) to avoid hangs on
  large grids; pass `None` to disable. Consolidation path enumeration has an
  analogous `DEFAULT_CONSOLIDATION_PATH_CUTOFF`.
- `OverFlowGraph` copies the caller's DataFrame in `__init__` (it never
  mutates the frame you pass in).

## Branch Policy for Claude Code Sessions

Development branch for code-quality work: **`claude/code-quality-analysis-8Ftgi`**.
Push all changes to that branch unless the user explicitly says otherwise.
Do not open PRs unless requested.
