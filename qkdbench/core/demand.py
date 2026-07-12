"""Key-delivery demands (ARCHITECTURE.md §3).

A :class:`Demand` describes *what* the network must deliver — a key
volume between two endpoints — independently of *how* any algorithm
serves it.  Static problems use ``volume_kb`` + ``deadline_slot``;
dynamic problems (v1.5) additionally use ``arrival_t`` / ``holding_t``.

``Request`` is kept as a backward-compatible alias of ``Demand``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Demand:
    """One key-delivery demand.

    Attributes:
        id: unique integer id within the instance.
        src / dst: endpoint node names.
        volume_kb: key volume (kb) that must be available to the pair.
        deadline_slot: last time slot (1-based, inclusive) by which the
            volume must have been delivered.
        priority: larger = more important (0 = default).
        arrival_t: arrival time for dynamic problems (``None`` = static,
            known at t=0).
        holding_t: how long the demand stays in the system (dynamic).
        rate_kbps: required sustained secret-key rate (kb/s) for dynamic
            admission problems (``None`` = static volume-based demand).
        metadata: free-form annotations only.
    """
    id: int
    src: str
    dst: str
    volume_kb: float
    deadline_slot: int
    priority: int = 0
    arrival_t: Optional[float] = None
    holding_t: Optional[float] = None
    rate_kbps: Optional[float] = None
    metadata: dict = field(default_factory=dict)


#: Backward-compatible alias — Phase 0 code and JSON used "Request".
Request = Demand
