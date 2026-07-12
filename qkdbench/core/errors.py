"""Benchmark-specific exceptions.

Every error a user can trigger through configuration or integration
raises one of these, with a message that says *what to fix* — never a
bare KeyError from deep inside the framework.
"""
from __future__ import annotations


class QKDBenchError(Exception):
    """Base class for all qkdbench errors."""


class ConfigError(QKDBenchError):
    """Invalid or inconsistent experiment configuration."""


class UnknownComponentError(QKDBenchError):
    """A name was not found in the registry."""

    def __init__(self, kind: str, name: str, available):
        super().__init__(
            f"unknown {kind} {name!r}; available: {sorted(available)}")
        self.kind, self.name = kind, name


class CapabilityError(QKDBenchError):
    """Scenario / problem / algorithm requirements do not match.

    Raised before execution, listing *all* mismatches, e.g.::

        Algorithm 'greedy_sp' does not support dynamic arrivals
        (problem declares decision 'admission_control').
    """

    def __init__(self, mismatches):
        self.mismatches = list(mismatches)
        super().__init__("incompatible experiment:\n  - "
                         + "\n  - ".join(self.mismatches))


class ValidationError(QKDBenchError):
    """An instance or solution failed schema/feasibility validation."""
