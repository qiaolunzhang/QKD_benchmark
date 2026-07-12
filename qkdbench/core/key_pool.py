"""Key pools (ARCHITECTURE.md §3).

A :class:`KeyPool` is a buffer of ready secret-key material associated
with a link.  In the dynamic admission problem (P2) each link's pool fills
at the link's QKD generation rate and is drawn down by the admitted
demands routed over that link; its inventory trajectory is the headline
QKD-specific metric (ordinary call-admission has no such store).

v1 dynamics are rate-based: a pool's generation rate ``gen_kbps`` is the
sustainable secret-key rate of its link, and an admission controller may
commit demands up to that rate (inventory then only accumulates, never
depletes).  Pool-burst admission — spending stored inventory to admit
above the generation rate for a bounded time — is a v1.5 extension.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class KeyPool:
    """A per-link store of ready key material.

    Attributes:
        pool_id: identifier, conventionally ``"a-b"`` for link (a, b).
        link: the link endpoints ``(a, b)`` with ``a <= b``.
        gen_kbps: secret-key generation rate of the link (kb/s), from the
            instance's QKD model.
        capacity_kb: maximum inventory the pool can hold.
        init_kb: inventory at t = 0.
        metadata: free-form annotations only.
    """
    pool_id: str
    link: tuple
    gen_kbps: float
    capacity_kb: float = 1e9
    init_kb: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["link"] = list(self.link)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "KeyPool":
        d = dict(d)
        d["link"] = tuple(d["link"])
        return cls(**d)
