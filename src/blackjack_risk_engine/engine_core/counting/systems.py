from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from blackjack_risk_engine.engine_core.cards import RANK_STRINGS, RankIndex


@dataclass(frozen=True, slots=True)
class CountSystem:
    system_id: str
    label: str
    balanced: bool
    ace_reckoned: bool
    level: int
    fractional: bool
    requires_ace_side_count: bool
    scaled_weights: tuple[int, ...]
    scale: int = 1

    def scaled_weight(self, rank: RankIndex) -> int:
        return self.scaled_weights[rank]


HI_LO = CountSystem(
    system_id="hi_lo",
    label="Hi-Lo",
    balanced=True,
    ace_reckoned=True,
    level=1,
    fractional=False,
    requires_ace_side_count=False,
    scaled_weights=(-1, 1, 1, 1, 1, 1, 0, 0, 0, -1),
)

HI_OPT_II = CountSystem(
    system_id="hi_opt_ii",
    label="Hi-Opt II",
    balanced=True,
    ace_reckoned=False,
    level=2,
    fractional=False,
    requires_ace_side_count=True,
    scaled_weights=(0, 1, 1, 2, 2, 1, 1, 0, 0, -2),
)

WONG_HALVES = CountSystem(
    system_id="wong_halves",
    label="Wong Halves",
    balanced=True,
    ace_reckoned=True,
    level=3,
    fractional=True,
    requires_ace_side_count=False,
    scaled_weights=(-2, 1, 2, 2, 3, 2, 1, 0, -1, -2),
    scale=2,
)

_SYSTEMS: tuple[CountSystem, ...] = (HI_LO, HI_OPT_II, WONG_HALVES)
COUNT_SYSTEMS: Mapping[str, CountSystem] = MappingProxyType(
    {system.system_id: system for system in _SYSTEMS}
)


def get_count_system(system_id: str) -> CountSystem:
    if not isinstance(system_id, str):
        raise ValueError("system_id must be a string")

    normalized_id = system_id.strip().lower()
    try:
        return COUNT_SYSTEMS[normalized_id]
    except KeyError as error:
        allowed = ", ".join(COUNT_SYSTEMS)
        raise ValueError(
            f"unknown count system {system_id!r}; expected one of: {allowed}"
        ) from error


def list_count_systems() -> tuple[CountSystem, ...]:
    return _SYSTEMS


def _validate_system_definitions() -> None:
    expected_weight_count = len(RANK_STRINGS)
    for system in _SYSTEMS:
        if len(system.scaled_weights) != expected_weight_count:
            raise RuntimeError(
                f"{system.system_id} must define one weight for each blackjack rank"
            )
        if system.scale <= 0:
            raise RuntimeError(f"{system.system_id} must use a positive scale")


_validate_system_definitions()
