from __future__ import annotations

import os
from typing import Literal, TypeAlias


EngineMode: TypeAlias = Literal["legacy", "deterministic", "hybrid", "monte_carlo"]
ENGINE_MODE_VALUES: tuple[EngineMode, ...] = ("legacy", "deterministic", "hybrid", "monte_carlo")
DEFAULT_ENGINE_MODE: EngineMode = "hybrid"


def normalize_engine_mode(value: str | None = None) -> EngineMode:
    raw_value = value if value is not None else os.getenv("ENGINE_MODE", DEFAULT_ENGINE_MODE)
    candidate = raw_value.strip().lower()
    if candidate in ENGINE_MODE_VALUES:
        return candidate  # type: ignore[return-value]

    allowed = ", ".join(ENGINE_MODE_VALUES)
    raise ValueError(f"engine_mode must be one of: {allowed}")
