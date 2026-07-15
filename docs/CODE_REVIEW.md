# ExpertOp4Grid — Architecture & Code Review

A large review of the `alphaDeesp` package covering code architecture,
interface & interaction design, performance & bottlenecks, and documentation
& maintainability — with a dedicated focus on `OverFlowGraph`, the class
consumed by other repositories.

The **[Follow-up: what was implemented](#follow-up-what-was-implemented)**
section at the end tracks which recommendations have already been actioned.

---

## How this review was conducted (principles & method)

1. **Read the seams, not just the lines.** Start from the public entry points
   (`main.py`, `expert_operator.py`, the `Simulation` ABC) and the module other
   repos import (`OverFlowGraph`). Architecture lives at the boundaries where a
   module hands control or data to another; debt concentrates there.
2. **Score the four concerns against one another.** Architecture, interface
   design, performance and maintainability trade off. A "clean" refactor that
   raises coupling is not a win.
3. **Distinguish invariants from code.** An undocumented invariant (row `i` ==
   line id; edge `color` strings encoding semantics) is a latent defect even
   when today's callers satisfy it.
4. **Severity = blast radius × likelihood × detectability.** A silent
   data-corruption bug in a cross-repo module outranks a style nit repeated 40
   times.
5. **Quick win vs. deep revision.** A quick win is local, low-risk, testable in
   isolation. A deep revision changes a contract or a layering decision and
   needs a migration path. Keep the two buckets separate.
6. **Verify claims against the code, not the docs.** Several `CLAUDE.md`
   assertions were stale; the source was trusted and the docs corrected.

**Overall assessment:** a healthy, actively-improving codebase. The split of
the monolithic `graphsAndPaths.py` into a typed `graphs/` package, the
rustworkx acceleration, the backward-compat shim, and a strong test suite
(~7.5k test LOC vs ~8.2k source LOC) are above the norm for a research-origin
expert system. Weaknesses were concentrated in a few correctness bugs, CI
pointing at the wrong files, a metric-driven refactor that traded cohesion for
coupling, and view/semantic entanglement inside `OverFlowGraph`.

---

## Strengths

- **Clean modular decomposition** of the graph layer: pure helpers
  (`graph_utils`), path algorithms (`shortest_paths`), the constrained-path
  value object, the structural analyzer, and the renderable graphs are
  separated and unit-tested.
- **Backward compatibility done right:** `graphsAndPaths.py` is a re-export
  shim with an explicit `__all__`, pinned by a contract test.
- **Typing and intent-capturing docstrings** in the new package.
- **A real quality pipeline** (`scripts/code_quality_report.py`; CI runs
  pyflakes + mypy + radon).
- **Deliberate deprecation** of the Pypownet backend rather than deletion.
- **Broad test coverage** of the graph package.

---

## Findings (bugs & correctness)

| # | Sev | Location | Issue | Status |
|---|-----|----------|-------|--------|
| 1 | ~~High~~ → readability | `graphs/overflow_graph.py` `rename_nodes` | **Correction:** the original was *functionally correct* — the `idx_ex` comprehension iterated the `idx_ex` column with a misleadingly-named `idx_or` loop variable. The initial "column corruption" grade was a misread, caught by adversarial re-verification. | **Clarified** (loop variable renamed; behaviour unchanged) |
| 2 | Med (latent) | `graphs/structured_overload_graph.py` `get_dispatch_edges_nodes` | `red_loops.Path.sum()` on an empty loop DataFrame returns the scalar `0`, so `set(0)` raises `TypeError` on any grid with no loop paths. | **Fixed** (explicit empty guard) |
| 3 | Med | `graphs/null_flow_graph.py` `_compute_sssp_paths` | bare `except Exception` silently swallowed Dijkstra failures. | **Fixed** (narrow catch + `logger.warning`) |
| 4 | Med | `core/simulation.py` `create_df` | positional label-indexing (`df[...][line_to_cut[0]]`) assumes a contiguous `RangeIndex` aligned to line ids. | Open (documented) |
| 5 | Med | `graphs/overflow_graph.py` `__init__` | mutated the caller's DataFrame (added `line_name`, `rename_nodes` rewrote columns). | **Fixed** (`df.copy()`) |
| 6 | Low | `graphs/shortest_paths.py` | dead branch + incomplete MultiDiGraph promoted-edge matching. | Open |
| 7 | Low | `core/alphadeesp.py` `to_DiGraph` | missing `capacity` defaults to `1.0`, skewing `rank_red_loops`. | Open |

> **On `find_loops` and the path cutoff (review perf item / QW3).** The
> `find_loops` code shipped with its `rx.all_simple_paths` cutoff *commented
> out* under a comment calling it "crucial to prevent hanging on large grids".
> Enabling it by default (cutoff = 10 nodes) was **itself a regression** —
> caught by the adversarial verification pass: rustworkx `cutoff` counts
> *nodes*, real RTE zone grids have loop paths of 15–42 nodes, so a default of
> 10 silently drops legitimate loops and can empty `find_loops` (triggering
> finding #2). The cutoff is therefore now an **opt-in parameter**
> (`loop_path_cutoff`, default `None` = unbounded = the original behaviour); the
> hang risk is documented and gateable rather than fixed by a lossy default.
> The analogous consolidation-path cutoff is likewise opt-in.

---

## Architecture

- **Metric-driven mixins reduced cohesion.** `NullFlowGraphMixin`,
  `GraphConsolidationMixin`, `TopologyScorerMixin`, `TopoApplicatorMixin` were
  extracted "to keep per-file LOC and average cyclomatic complexity within
  A-grade bounds" — an implicit interface with no enforcement (each documents
  "assumes the concrete class provides `self.g` …"). Prefer composition or a
  `typing.Protocol` so the required surface is enforced. *(Deep revision — not
  taken this pass, by request.)*
- **`OverFlowGraph` fused construction + rendering + semantic tagging.**
  Addressed by the model/renderer split (below).
- **`Structured_Overload_Distribution_Graph.__init__` does heavy work eagerly**
  (multiple full-graph copies) and the consolidation loop rebuilds the whole
  object each iteration. Copy count reduced (below); the eager-construction /
  staged-`run()` shape remains a future revision.
- **`AlphaDeesp.__init__` does everything** (ranking runs in the constructor;
  `AlphaDeesp_warmStart` exists to skip it) — a candidate for an explicit
  `run()` API.

## Interface & interaction design

- The `Simulation` ABC is the best-designed surface — keep it as the template.
- Naming is mixed (`snake_case` / `camelCase` / `Structured_..._Graph`) and is
  load-bearing on the abstract contract and external importers. Prefer PEP8
  forwarding aliases + a deprecation clock over hard renames.
- French/English domain terms (`amont`/`aval`) leak into the API; a short
  glossary in the docs would remove onboarding friction.
- The config key `ThersholdMinPowerOfLoop` is misspelled and effectively
  public; accept both spellings rather than renaming.

## Performance & bottlenecks

- **`find_loops`** — missing cutoff + `O(n²)` source/target enumeration.
  **Fixed** (cutoff re-enabled/configurable).
- **Repeated full-graph copies** — `delete_color_edges` copies per call; the
  structured graph chained ~7 copies. **Fixed** (multi-colour `delete_color_edges`,
  single-pass derived graphs).
- **`iterrows` hot loops in ranking** — `sort_hubs` (`O(hubs × rows)`) and
  `_initial_inflow_between` (`O(buses × edges × rows)`). **Fixed** (group-sum
  vectorisation + a precomputed inflow lookup).
- `create_df` makes several `iterrows` passes (backend data-prep, exercised by
  the grid2op suite) — left for a follow-up with grid2op available.

## Documentation & maintainability

- **`CLAUDE.md` had drifted** (described `graphsAndPaths.py` as the real module;
  claimed the codebase was untyped and used star imports; stale Python
  version). **Refreshed.**
- **CI lints/type-checks the shim, not the package.** `.circleci/config.yml`
  runs pyflakes/mypy on the 49-line `graphsAndPaths.py`, never on
  `graphs/overflow_graph.py` etc. — so the cross-repo module has no static gate.
  **Recommended fix (not taken this pass, by request):** point CI at the
  `graphs/` package.
- `stdout` printing vs logging is inconsistent in the older backends.
- `interactive_html.py` (~976 LOC) and `Grid2opSimulation.py` (~814 LOC) are
  the remaining maintainability hotspots.

---

## Focus: `OverFlowGraph` (the cross-repo interface)

**Strengths:** the shim + `__all__` keep the import path stable; the move to
explicit source-of-truth semantic flags (`is_overload`, `is_monitored`,
`in_red_loop`, `on_constrained_path`, `is_hub`, `is_extra_cut`) is the right
direction — downstream consumers query semantics without reverse-engineering
colours.

**What was undermining it, and what changed:**

1. **Rendering and analysis were fused in one class.** Now split into a
   **semantic model** (`OverFlowGraph`) and a stateless **renderer**
   (`OverflowGraphRenderer`) that owns all Graphviz vocabulary (penwidth,
   shapes, tapered styling, compound `"colour:yellow:colour"` strings, HTML
   labels, plotting). Other repos can reuse the renderer on any semantic graph,
   or depend on the model without pulling in Graphviz concerns. Public method
   signatures are unchanged; the renderer is exported from both the package and
   the shim.
2. **Caller-DataFrame mutation** and the **`rename_nodes` bug** — both fixed.
3. **Semantics still partly ride on Graphviz colour strings** (e.g.
   `tag_constrained_path` splits `"coral:yellow:coral"`). Fully inverting this
   (model authoritative, colours derived) remains a future revision.
4. **No published API contract / version discipline for behaviour.** The
   package's public *names* are pinned by `test_graphs_package.py`; behavioural
   flags are pinned by `test_overflow_graph.py`. Extending semver discipline to
   behaviour changes is recommended.

---

## Follow-up: what was implemented

This pass implemented review recommendations 1, 3, 4, 5 (skipping #2, the CI
repoint), plus the two named performance items and the `OverFlowGraph`
model/renderer deep revision, and refreshed `CLAUDE.md`.

| Recommendation | Change | Tests |
|---|---|---|
| QW1 — `rename_nodes` | loop variable renamed for clarity (behaviour was already correct — see finding #1) | `TestRenameNodes` |
| QW3 — cutoff in `find_loops` + other path sites | opt-in `loop_path_cutoff` / `DEFAULT_CONSOLIDATION_PATH_CUTOFF`, **default `None`** (unbounded = original behaviour); plus an empty-loops guard in `get_dispatch_edges_nodes` (finding #2) | `TestStructuredOverloadDistributionGraphNoLoops`, existing structured-graph tests |
| QW4 — stop mutating caller df | `OverFlowGraph.__init__` copies the frame | `TestDoesNotMutateCallerDataFrame` |
| QW5 — narrow the bare `except` | `(nx.NetworkXException, ValueError)` + `logger.warning` | existing null-flow tests |
| Perf — repeated full-graph copies | `delete_color_edges` accepts multiple colours (single copy); structured graph builds each derived view in one pass | `test_graph_utils`, `test_graphs_package` |
| Perf — `iterrows` in ranking | `sort_hubs` group-sum vectorisation; `_build_inflow_lookup` precompute (kept `_initial_inflow_between` as fallback) | `TestSortHubs`, `TestBuildInflowLookup`, `TestBusLoopStrength` |
| Deep — split `OverFlowGraph` | new `OverflowGraphRenderer` (Graphviz presentation); `OverFlowGraph` delegates rendering, keeps the semantic model | `test_overflow_renderer.py`, `test_overflow_graph.py` |
| Docs | `docs/CODE_REVIEW.md` (this file); `CLAUDE.md` refreshed | — |

**Not taken this pass (by request):** recommendation #2 (repoint CI static
analysis at the `graphs/` package) and the mixins → composition/Protocol deep
revision. Both remain recommended.

**Validation.** The graph-package + ranking + renderer + interactive-html unit
suites pass locally without grid2op (342 tests). In addition, an **adversarial
multi-agent verification pass** (5 independent lenses) was run over the
behaviour-preserving changes:

- `delete_color_edges` single-pass union, the `_build_inflow_lookup` /
  `sort_hubs` vectorisations, the `OverFlowGraph` model/renderer split, the
  `except` narrowing, and the `df.copy()` were all **verified equivalent**
  (including a 20k-trial differential fuzz of the ranking helpers).
- The pass **caught two real issues**: the `find_loops` default-cutoff
  regression (now reverted to opt-in) and the misread severity of the
  `rename_nodes` finding (now corrected above).

The grid2op integration suites (`alphadeesp_test.py`, `test_expert_op.py`,
`test_expert_rules.py`, the `grid2op/` tests) require `grid2op` +
`lightsim2grid` and were **not** run in this environment. With the cutoffs now
defaulting to `None`, the graph-analysis behaviour on those grids is unchanged
from `master`; running them in CI remains the recommended confirmation.
