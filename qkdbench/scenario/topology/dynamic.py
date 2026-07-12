"""DynamicTopology interface — **placeholder, not implemented in v1**.

Reserved for v1.5 (dynamic problems, ARCHITECTURE.md §4 / §13): a
time-varying topology exposes snapshots and the event stream between two
instants (link up/down, node failure).  v1 experiments are static, so
this ABC only fixes the vocabulary; every method raises
``NotImplementedError`` and no provider is registered.
"""
from __future__ import annotations

from abc import ABC
from typing import Optional

from ...core.network import Network


class DynamicTopology(ABC):
    """Time-varying topology (v1.5+).

    Planned contract:

    * ``snapshot(t)`` — the :class:`Network` in force at time ``t``.
    * ``events(t0, t1)`` — chronological list of topology events in
      ``(t0, t1]``; v1.5 event kinds are limited to arrival / departure
      / failure (no full DES simulator — that is SimQN territory).
    """

    capabilities = {"dynamic"}

    def snapshot(self, t: float) -> Network:
        raise NotImplementedError(
            "DynamicTopology is a v1.5 placeholder (ARCHITECTURE.md §13)")

    def events(self, t0: float, t1: Optional[float] = None):
        raise NotImplementedError(
            "DynamicTopology is a v1.5 placeholder (ARCHITECTURE.md §13)")
