"""Domain policies for signal design."""

from __future__ import annotations

from typing import Any

from backend.fire_alarm_placement import calculate_fire_alarm_layout
from backend.signal_planning import calculate_zkspc_layout, recalculate_cable_routes, route_length_m


class ZkspcPlanningPolicy:
    """Encapsulates automatic ZKSPC layout rules."""

    @staticmethod
    def detect(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return calculate_zkspc_layout(rooms)


class FireAlarmLayoutPolicy:
    """Encapsulates branch-specific fire alarm layout preview."""

    @staticmethod
    def preview(plan_data: dict[str, Any], *, scale_factor: float, system_type: str, zkspc_zones: list[dict[str, Any]]) -> dict[str, Any]:
        return calculate_fire_alarm_layout(
            plan_data,
            scale_factor=scale_factor,
            system_type=system_type,
            zkspc_zones=zkspc_zones,
        )


class CableRoutingPolicy:
    """Encapsulates cable routing and length calculation."""

    @staticmethod
    def recalculate(
        plan_data: dict[str, Any],
        *,
        system_type: str,
        instrument: dict[str, Any],
        alarms: list[dict[str, Any]],
        use_shared_trunk: bool,
    ) -> list[dict[str, Any]]:
        return recalculate_cable_routes(
            plan_data,
            system_type=system_type,
            instrument=instrument,
            alarms=alarms,
            use_shared_trunk=use_shared_trunk,
        )

    @staticmethod
    def length(points: list[list[float]], scale_factor: float) -> float:
        return route_length_m(points, scale_factor)
