# Copyright (c) 2019-2020, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of ExpertOp4Grid, an expert system approach to solve flow congestions in power grids

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

import pandas as pd

from alphaDeesp.core.elements import Consumption, ExtremityLine, OriginLine, Production

logger = logging.getLogger(__name__)

# Convenience alias for the heterogeneous per-substation element lists.
SubstationElement = Union[Production, Consumption, OriginLine, ExtremityLine]


class Simulation(ABC):
    """Abstract Class Simulation"""

    #: Backend-provided runtime configuration (thresholds, layout, etc.)
    #: populated by concrete subclasses in their own ``__init__``.
    param_options: Dict[str, Any]
    #: Debug flag consulted by :meth:`create_df`; concrete subclasses set it.
    debug: bool

    def __init__(self) -> None:
        super().__init__()


    @abstractmethod
    def cut_lines_and_recomputes_flows(self, ids: List[int]) -> Sequence[float]:
        """Disconnect the lines identified by ``ids`` and re-run a power flow.

        Implementations must not mutate the long-lived simulation state
        beyond what is needed to compute the new flows (overload
        disconnection parameters, for example, should be restored before
        returning).

        :param ids: list of internal line ids (as used by the backend) to
            switch off before recomputing the flows.
        :returns: A sequence of post-cut line flows (``numpy.ndarray`` or
            similar), aligned on the backend's line ordering. The values
            are used by :meth:`create_df` to fill the ``new_flows`` column.
        """

    @abstractmethod
    def isAntenna(self) -> Optional[int]:
        """Return the substation id of an antenna attached to the overloaded line, if any.

        An "antenna" is a substation where the overloaded line is the only
        line connected at a given busbar; splitting such a substation cannot
        help relieving the overload and AlphaDeesp uses this information to
        prune candidate topologies.

        :returns: The external substation id of the antenna, or ``None`` if
            the overloaded line is not attached to an antenna.
        """

    @abstractmethod
    def isDoubleLine(self) -> Optional[List[int]]:
        """Return the list of parallel lines sharing the endpoints of the overloaded line.

        Two substations may be connected by more than one line ("double
        line"); AlphaDeesp needs to know this because topology actions on
        either endpoint behave differently from the single-line case.

        :returns: A list of backend line ids that run in parallel to the
            current overloaded line (``self.ltc[0]``), or ``None`` if there
            is no parallel line.
        """

    @abstractmethod
    def getLinesAtSubAndBusbar(self) -> Dict[Any, List[int]]:
        """Return the lines connected to each endpoint substation, grouped by busbar.

        Used by :meth:`isAntenna` and by the ranking step to count the
        degree of each busbar around the overloaded line.

        :returns: A ``dict`` keyed by ``(substation_id, busbar_id)`` (or a
            backend-specific equivalent) whose values are the list of line
            ids connected at that busbar.
        """

    @abstractmethod
    def get_layout(self) -> List[Tuple[float, float]]:
        """Return the 2D coordinates of each substation for plotting.

        :returns: A list of ``(x, y)`` tuples, one per substation, in the
            order used by the backend (``[(x1, y1), (x2, y2), ...]``).
        """

    @abstractmethod
    def get_substation_in_cooldown(self) -> List[int]:
        """Return substations that cannot be acted upon at the current timestep.

        Some backends (notably Grid2op) enforce a cooldown period after a
        topology change; substations still in cooldown must be excluded
        from the candidate set.

        :returns: A list of substation ids currently in cooldown.
        """

    @abstractmethod
    def get_substation_elements(self) -> Dict[int, List[SubstationElement]]:
        """Return the per-substation element model built from the observation.

        Each element is an instance of one of the classes in
        :mod:`alphaDeesp.core.elements` (``Production``, ``Consumption``,
        ``OriginLine``, ``ExtremityLine``). AlphaDeesp consumes this mapping
        to enumerate busbar configurations.

        :returns: A ``dict`` mapping substation id (int) to the list of
            element objects attached to that substation.
        """

    @abstractmethod
    def get_substation_to_node_mapping(self) -> Optional[Dict[int, Any]]:
        """Return the mapping from substation ids to overflow-graph node ids.

        Depending on the backend a substation may map to one or two nodes
        (one per busbar); this mapping is used to translate AlphaDeesp's
        internal graph back to substation-level actions.

        :returns: A ``dict`` keyed by substation id whose values are node
            ids in the overflow graph, or ``None`` if the backend uses a
            1-to-1 mapping and does not need the translation table.
        """

    @abstractmethod
    def get_internal_to_external_mapping(self) -> Dict[int, int]:
        """Return the translation table from internal node ids to backend ids.

        AlphaDeesp renumbers substations densely starting at 0 for its
        graph algorithms; this mapping is used to emit topology actions
        that reference the original backend ids.

        :returns: A ``dict`` keyed by internal (AlphaDeesp) node id whose
            values are the corresponding backend substation ids.
        """

    @abstractmethod
    def get_dataframe(self) -> pd.DataFrame:
        """Return the main topology + flow dataframe produced by :meth:`create_df`.

        The dataframe has one row per line of the grid and at least the
        columns ``idx_or``, ``idx_ex``, ``init_flows``, ``new_flows``,
        ``delta_flows``, ``swapped`` and ``gray_edges``. It is the primary
        input of the AlphaDeesp ranking step.

        :returns: A ``pandas.DataFrame`` representing the overloaded grid.
        """

    @abstractmethod
    def get_reference_topovec_sub(self, sub: int) -> List[int]:
        """Return the all-on-busbar-1 topology vector for substation ``sub``.

        AlphaDeesp uses this vector as the "do nothing" reference when
        ranking candidate busbar splits.

        :param sub: Backend substation id.
        :returns: A list of integers, one per element attached to ``sub``,
            all initialized to the reference busbar (typically 0 or 1
            depending on the backend convention).
        """

    @abstractmethod
    def get_overload_disconnection_topovec_subor(self, l: int) -> Tuple[int, List[int]]:
        """Return the topology vector that disconnects the origin side of line ``l``.

        This is used to simulate a line-opening action as a degenerate
        topology change on the ``origin`` substation.

        :param l: Backend line id (typically the overloaded line).
        :returns: A ``(substation_id, topo_vect)`` tuple where
            ``topo_vect`` has ``-1`` at the element position corresponding
            to the origin side of ``l`` (meaning "disconnected") and
            preserves the current assignment elsewhere.
        """

    @staticmethod
    def create_end_result_empty_dataframe() -> pd.DataFrame:
        """This function creates initial structure for the dataframe"""

        end_result_dataframe_structure_initiation: Dict[str, List[Any]] = {
            "overflow ID": [],
            "Flows before": [],
            "Flows after": [],
            "Delta flows": [],
            "Worsened line": [],
            "Prod redispatched": [],
            "Load redispatched": [],
            "Internal Topology applied ": [],
            "Topology applied": [],
            "Substation ID": [],
            "Rank Substation ID": [],
            "Topology score": [],
            "Topology simulated score": [],
            "Efficacity": [],
        }
        end_result_data_frame = pd.DataFrame(end_result_dataframe_structure_initiation)

        return end_result_data_frame

    def create_df(self, d: Dict[str, Any], line_to_cut: List[int]) -> pd.DataFrame:
        """Build the topology + flow DataFrame for a cut line.

        ``d`` represents a topology (one row per grid line, in line-id order).
        The row-per-line ordering is a load-bearing invariant: the overloaded
        line's delta flow is read positionally by ``line_to_cut`` id, and
        ``OverFlowGraph`` matches ``lines_to_cut`` against row positions too.
        The former ``iterrows`` passes are vectorised with numpy masks; the
        numerical results are identical.
        """
        # HERE WE CREATE DATAFRAME
        df = pd.DataFrame(d["edges"])
        pd.set_option("display.float_format", lambda x: "%.3f" % x)

        # takes a dataframe and swaps branches init_flows < 0
        self.branch_direction_swaps(df)

        new_flows = np.asarray(self.cut_lines_and_recomputes_flows(line_to_cut), dtype=float)
        swapped = df["swapped"].to_numpy()

        # here we multiply by (-1) new flows that are reversed
        new_flows_signed = np.where(swapped, -new_flows, new_flows)
        df["new_flows"] = new_flows_signed

        init_flows = df["init_flows"].to_numpy(dtype=float)
        abs_new = np.abs(new_flows_signed)
        abs_init = np.abs(init_flows)

        # if new_flows < 0, and abs(new) > abs(init) then True (we invert edge direction) else False
        new_flows_swapped = (new_flows_signed < 0) & (abs_new > abs_init)
        df["new_flows_swapped"] = new_flows_swapped

        # now we add delta flows
        # report = abs(new) - abs(init) if the flow did not change direction.
        # If it did there are two cases:
        #   * new_flows_swapped -> the edge is inverted: report = abs(new) + abs(init)
        #   * opposite signs (both non-zero) -> discharged: report = -(abs(new) + abs(init))
        opposite_sign = (
            (np.sign(new_flows_signed) != np.sign(init_flows))
            & (new_flows_signed != 0)
            & (init_flows != 0)
        )
        # ``elif`` semantics: opposite_sign only applies where new_flows_swapped is False.
        discharged = opposite_sign & ~new_flows_swapped
        delta_flo = np.where(
            new_flows_swapped, abs_new + abs_init,
            np.where(discharged, -(abs_new + abs_init), abs_new - abs_init),
        )
        df["delta_flows"] = delta_flo

        # swap origin/extremity (and abs the init flow) on inverted edges
        idx_or = df["idx_or"].to_numpy()
        idx_ex = df["idx_ex"].to_numpy()
        df["idx_or"] = np.where(new_flows_swapped, idx_ex, idx_or)
        df["idx_ex"] = np.where(new_flows_swapped, idx_or, idx_ex)
        df["init_flows"] = np.where(new_flows_swapped, abs_init, init_flows)

        # now we identify gray edges (below-significance redispatch).
        # ``.iloc`` makes the positional (row == line id) access explicit.
        ltc_report = float(df["delta_flows"].abs().iloc[line_to_cut[0]])
        max_overload = ltc_report * float(self.param_options["ThresholdReportOfLine"])
        df["gray_edges"] = df["delta_flows"].abs().to_numpy() < max_overload

        if getattr(self, "debug", False):
            logger.debug("==== After gray_edges added IN FUNCTION CREATE DF ====")
            logger.debug("%s", df)

        return df

    @staticmethod
    def branch_direction_swaps(df: pd.DataFrame) -> None:
        """Invert branches whose ``init_flows`` is negative (draw them forward).

        Vectorised replacement for the former ``iterrows`` loop; identical
        results. Rows with ``init_flows < 0`` get their origin/extremity swapped,
        their ``init_flows`` made positive, and ``swapped=True``.
        """
        init = df["init_flows"].to_numpy(dtype=float)
        swap_mask = (init < 0) & (init != 0.0)

        idx_or = df["idx_or"].to_numpy()
        idx_ex = df["idx_ex"].to_numpy()
        df["idx_or"] = np.where(swap_mask, idx_ex, idx_or)
        df["idx_ex"] = np.where(swap_mask, idx_or, idx_ex)
        df["init_flows"] = np.where(swap_mask, np.abs(init), init)
        df["swapped"] = swap_mask

    @staticmethod
    def invert_dict_keys_values(d: Dict[Any, Any]) -> Dict[Any, Any]:
        return dict([(v, k) for k, v in d.items()])

    @staticmethod
    def get_model_obj_from_or(
        df_indexed: pd.DataFrame,
        substation_id: int,
        dest: int,
        busbar: int,
    ) -> Optional[Union[OriginLine, ExtremityLine]]:
        try:
            # Case 1: Direct Match
            val = df_indexed.loc[(substation_id, dest), 'delta_flows']

            # Handle duplicates: if multiple rows match, val is a Series
            if isinstance(val, pd.Series):
                val = val.iloc[0]  # Take the first one

            # Ensure it's a list for the constructor
            return OriginLine(busbar, dest, [val])

        except KeyError:
            # Case 2: Swapped Match
            try:
                row = df_indexed.loc[(dest, substation_id)]

                # --- FIX STARTS HERE ---
                # If we get a DataFrame (multiple matches), take the first row
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                # --- FIX ENDS HERE ---

                val = [row['delta_flows']]

                # Now 'row' is guaranteed to be a Series, so these are single scalars
                if row['swapped'] == row['new_flows_swapped']:
                    return OriginLine(busbar, dest, val)
                else:
                    return ExtremityLine(busbar, dest, val)

            except KeyError:
                return None

    @staticmethod
    def get_model_obj_from_ext(
        df_indexed: pd.DataFrame,
        substation_id: int,
        dest: int,
        busbar: int,
    ) -> Optional[Union[OriginLine, ExtremityLine]]:
        """
        Optimized version using Pandas MultiIndex, robust against Duplicate Rows.
        """
        try:
            # Case 1: Direct Match (idx_or == dest AND idx_ex == substation_id)
            # We look up the 'delta_flows' column directly
            val = df_indexed.loc[(dest, substation_id), 'delta_flows']

            # FIX 1: Handle if multiple rows match (returns Series instead of scalar)
            if isinstance(val, pd.Series):
                val = val.iloc[0]

            return ExtremityLine(busbar, dest, [val])

        except KeyError:
            # Case 2: Swapped Match (idx_or == substation_id AND idx_ex == dest)
            try:
                row = df_indexed.loc[(substation_id, dest)]

                # FIX 2: Handle if multiple rows match (returns DataFrame instead of Series)
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]  # Take the first row

                val = [row['delta_flows']]

                # Now 'row' is definitely a Series, so these comparisons result in a single Boolean
                # Logic: If swapped status matches new_flows_swapped -> It behaves like an ExtremityLine
                if row['swapped'] == row['new_flows_swapped']:
                    return ExtremityLine(busbar, dest, val)
                else:
                    return OriginLine(busbar, dest, val)

            except KeyError:
                # Case 3: Line not found in either direction
                return None