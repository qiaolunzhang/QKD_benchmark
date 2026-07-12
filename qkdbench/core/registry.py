"""Unified component registry.

One registry, many kinds (algorithm, topology, qkd_model, traffic,
decision, constraint, objective, metric, ...).  Decorator-based:
importing a module registers its components, which keeps discovery
simple and debuggable (ARCHITECTURE.md §11).

    from qkdbench.core.registry import registry

    @registry.register("qkd_model", "constant")
    class ConstantRate: ...

    cls = registry.get("qkd_model", "constant")
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict

from .errors import UnknownComponentError


class Registry:
    def __init__(self):
        self._by_kind: Dict[str, Dict[str, type]] = defaultdict(dict)

    def register(self, kind: str, name: str = None):
        """Class decorator: ``@registry.register("metric", "acceptance")``.

        Falls back to the class attribute ``name`` when the second
        argument is omitted.
        """
        def deco(cls):
            key = name or getattr(cls, "name", None)
            if not key:
                raise ValueError(
                    f"{cls.__name__}: no registry name given and no "
                    f"`name` class attribute")
            existing = self._by_kind[kind].get(key)
            if existing is not None and existing is not cls:
                raise ValueError(
                    f"{kind} {key!r} already registered by "
                    f"{existing.__name__}")
            self._by_kind[kind][key] = cls
            return cls
        return deco

    def get(self, kind: str, name: str) -> type:
        try:
            return self._by_kind[kind][name]
        except KeyError:
            raise UnknownComponentError(kind, name,
                                        self._by_kind.get(kind, {})) from None

    def names(self, kind: str):
        return sorted(self._by_kind.get(kind, {}))

    def kinds(self):
        return sorted(self._by_kind)


#: process-global registry used by all component decorators
registry = Registry()
