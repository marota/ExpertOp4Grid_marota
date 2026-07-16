"""Unit tests for the backend-agnostic static helpers on
:class:`alphaDeesp.core.simulation.Simulation` — the MultiIndex line-model
lookups and the small dict / empty-frame utilities. No grid2op backend needed.
"""

import pandas as pd

from alphaDeesp.core.simulation import Simulation
from alphaDeesp.core.elements import ExtremityLine, OriginLine


def _indexed(rows):
    """Build the (idx_or, idx_ex)-indexed DataFrame the lookups expect."""
    return pd.DataFrame(rows).set_index(["idx_or", "idx_ex"])


class TestGetModelObjFromOr:
    def test_direct_match_returns_origin_line(self):
        df = _indexed({
            "idx_or": [1], "idx_ex": [2], "delta_flows": [5.0],
            "swapped": [False], "new_flows_swapped": [False],
        })
        obj = Simulation.get_model_obj_from_or(df, substation_id=1, dest=2, busbar=0)
        assert isinstance(obj, OriginLine)
        assert obj.end_substation_id == 2 and obj.flow_value == [5.0] and obj.busbar_id == 0

    def test_duplicate_rows_take_first(self):
        df = _indexed({
            "idx_or": [1, 1], "idx_ex": [2, 2], "delta_flows": [5.0, 7.0],
            "swapped": [False, False], "new_flows_swapped": [False, False],
        })
        obj = Simulation.get_model_obj_from_or(df, 1, 2, 0)
        assert obj.flow_value == [5.0]

    def test_swapped_match_same_flag_is_origin_line(self):
        df = _indexed({
            "idx_or": [2], "idx_ex": [1], "delta_flows": [5.0],
            "swapped": [True], "new_flows_swapped": [True],
        })
        obj = Simulation.get_model_obj_from_or(df, substation_id=1, dest=2, busbar=0)
        assert isinstance(obj, OriginLine)

    def test_swapped_match_diff_flag_is_extremity_line(self):
        df = _indexed({
            "idx_or": [2], "idx_ex": [1], "delta_flows": [5.0],
            "swapped": [True], "new_flows_swapped": [False],
        })
        obj = Simulation.get_model_obj_from_or(df, substation_id=1, dest=2, busbar=0)
        assert isinstance(obj, ExtremityLine)

    def test_no_match_returns_none(self):
        df = _indexed({
            "idx_or": [9], "idx_ex": [10], "delta_flows": [1.0],
            "swapped": [False], "new_flows_swapped": [False],
        })
        assert Simulation.get_model_obj_from_or(df, 1, 2, 0) is None


class TestGetModelObjFromExt:
    def test_direct_match_returns_extremity_line(self):
        # from_ext direct match is (dest, substation_id)
        df = _indexed({
            "idx_or": [2], "idx_ex": [1], "delta_flows": [5.0],
            "swapped": [False], "new_flows_swapped": [False],
        })
        obj = Simulation.get_model_obj_from_ext(df, substation_id=1, dest=2, busbar=0)
        assert isinstance(obj, ExtremityLine)
        assert obj.start_substation_id == 2 and obj.flow_value == [5.0]

    def test_swapped_match_diff_flag_is_origin_line(self):
        df = _indexed({
            "idx_or": [1], "idx_ex": [2], "delta_flows": [5.0],
            "swapped": [True], "new_flows_swapped": [False],
        })
        obj = Simulation.get_model_obj_from_ext(df, substation_id=1, dest=2, busbar=0)
        assert isinstance(obj, OriginLine)

    def test_no_match_returns_none(self):
        df = _indexed({
            "idx_or": [9], "idx_ex": [10], "delta_flows": [1.0],
            "swapped": [False], "new_flows_swapped": [False],
        })
        assert Simulation.get_model_obj_from_ext(df, 1, 2, 0) is None


class TestSmallHelpers:
    def test_invert_dict_keys_values(self):
        assert Simulation.invert_dict_keys_values({1: "a", 2: "b"}) == {"a": 1, "b": 2}

    def test_create_end_result_empty_dataframe(self):
        df = Simulation.create_end_result_empty_dataframe()
        assert len(df) == 0
        for col in ("overflow ID", "Flows before", "Efficacity", "Substation ID"):
            assert col in df.columns
