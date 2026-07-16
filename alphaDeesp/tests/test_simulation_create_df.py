"""Differential tests for the vectorised ``Simulation.create_df``.

``create_df`` used to run several ``iterrows`` passes; it is now vectorised with
numpy masks. Because the end-to-end path needs a grid2op backend (unavailable in
the unit environment), we pin equivalence by comparing the vectorised output
against a faithful re-implementation of the *original* row-by-row logic across a
fuzz of random inputs, plus a couple of hand-checked cases.
"""

import math

import numpy as np
import pandas as pd

from alphaDeesp.core.simulation import Simulation


# ── Minimal host exposing create_df / branch_direction_swaps without ABC ──
class _Host:
    create_df = Simulation.create_df
    branch_direction_swaps = staticmethod(Simulation.branch_direction_swaps)

    def __init__(self, new_flows, threshold=0.2):
        self._new_flows = np.asarray(new_flows, dtype=float)
        self.param_options = {"ThresholdReportOfLine": threshold}
        self.debug = False

    def cut_lines_and_recomputes_flows(self, ids):
        return self._new_flows


# ── Faithful re-implementation of the ORIGINAL iterrows logic ──
def _reference_create_df(edges, new_flows, threshold, line_to_cut):
    df = pd.DataFrame(edges)

    swapped = []
    for i, row in df.iterrows():
        a = row["init_flows"]
        if a < 0 and a != 0.0:
            idx_or = row["idx_or"]
            df.at[i, "idx_or"] = row["idx_ex"]
            df.at[i, "idx_ex"] = idx_or
            df.at[i, "init_flows"] = math.fabs(row["init_flows"])
            swapped.append(True)
        else:
            swapped.append(False)
    df["swapped"] = swapped

    n_flows = [f * -1 if sw else f for f, sw in zip(new_flows, df["swapped"])]
    df["new_flows"] = n_flows

    nfs = []
    for _, row in df.iterrows():
        nfs.append(row["new_flows"] < 0 and math.fabs(row["new_flows"]) > math.fabs(row["init_flows"]))
    df["new_flows_swapped"] = nfs

    delta_flo = []
    for i, row in df.iterrows():
        if row["new_flows_swapped"]:
            delta_flo.append(math.fabs(row["new_flows"]) + math.fabs(row["init_flows"]))
            idx_or = row["idx_or"]
            df.at[i, "idx_or"] = row["idx_ex"]
            df.at[i, "idx_ex"] = idx_or
            df.at[i, "init_flows"] = math.fabs(row["init_flows"])
        elif (np.sign(row["new_flows"]) != np.sign(row["init_flows"])) and (row["new_flows"] != 0) and (row["init_flows"] != 0):
            delta_flo.append(-(math.fabs(row["new_flows"]) + math.fabs(row["init_flows"])))
        else:
            delta_flo.append(math.fabs(row["new_flows"]) - math.fabs(row["init_flows"]))
    df["delta_flows"] = delta_flo

    gray_edges = []
    ltc_report = df["delta_flows"].abs()[line_to_cut[0]]
    max_overload = ltc_report * float(threshold)
    for edge_value in df["delta_flows"]:
        gray_edges.append(math.fabs(edge_value) < max_overload)
    df["gray_edges"] = gray_edges
    return df


_COLS = ["idx_or", "idx_ex", "init_flows", "new_flows",
         "new_flows_swapped", "delta_flows", "swapped", "gray_edges"]


def _assert_equivalent(edges, new_flows, threshold, line_to_cut):
    got = _Host(new_flows, threshold).create_df({"edges": edges}, line_to_cut)
    ref = _reference_create_df(edges, new_flows, threshold, line_to_cut)
    for col in _COLS:
        g = got[col].to_numpy()
        r = ref[col].to_numpy()
        if g.dtype.kind == "f" or r.dtype.kind == "f":
            np.testing.assert_allclose(g.astype(float), r.astype(float), atol=1e-12,
                                       err_msg=f"column {col} differs")
        else:
            np.testing.assert_array_equal(g, r, err_msg=f"column {col} differs")


class TestCreateDfEquivalence:

    def test_hand_crafted_mixed_case(self):
        edges = {
            "idx_or":     [0, 1, 2, 3],
            "idx_ex":     [1, 2, 3, 0],
            "init_flows": [10.0, -5.0, 0.0, 8.0],
        }
        # new flows: sign flip, overload, zero, mild change
        new_flows = [-20.0, 3.0, 0.0, 9.0]
        _assert_equivalent(edges, new_flows, 0.2, [0])

    def test_all_zero_flows(self):
        edges = {"idx_or": [0, 1], "idx_ex": [1, 2], "init_flows": [0.0, 0.0]}
        _assert_equivalent(edges, [0.0, 0.0], 0.2, [0])

    def test_fuzz_matches_reference(self):
        rng = np.random.default_rng(20260716)
        for _ in range(400):
            n = int(rng.integers(2, 9))
            edges = {
                "idx_or": list(rng.integers(0, n, size=n)),
                "idx_ex": list(rng.integers(0, n, size=n)),
                # include negatives, zeros and positives
                "init_flows": list(np.round(rng.uniform(-50, 50, size=n), 3)),
            }
            new_flows = list(np.round(rng.uniform(-80, 80, size=n), 3))
            # occasionally force exact zeros to exercise sign(0) edge cases
            if rng.random() < 0.3:
                edges["init_flows"][int(rng.integers(0, n))] = 0.0
            if rng.random() < 0.3:
                new_flows[int(rng.integers(0, n))] = 0.0
            line_to_cut = [int(rng.integers(0, n))]
            _assert_equivalent(edges, new_flows, 0.2, line_to_cut)

    def test_positional_index_is_used_for_ltc_report(self):
        # A non-overloaded first row and a big overload elsewhere: the gray
        # threshold must be computed from line_to_cut's row, positionally.
        edges = {"idx_or": [0, 1, 2], "idx_ex": [1, 2, 0],
                 "init_flows": [1.0, 1.0, 1.0]}
        new_flows = [1.0, 1.0, 100.0]  # row 2 is the big delta
        got = _Host(new_flows, 0.2).create_df({"edges": edges}, [2])
        # ltc_report = |delta[2]| = 99; max_overload = 19.8; rows 0,1 (~0) are gray
        assert bool(got["gray_edges"].iloc[0]) is True
        assert bool(got["gray_edges"].iloc[2]) is False
