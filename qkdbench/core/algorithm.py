"""Algorithm base class and registry.

Integrating a new algorithm takes one file and three steps:

    from qkdbench import Algorithm, register_algorithm

    @register_algorithm
    class MyAlgo(Algorithm):
        name = "my_algo"

        def solve(self, instance):
            ...  # build and return a Solution

The benchmark runner discovers it by name (``qkdbench run`` or
``get_algorithm("my_algo")``), runs it on the shared instances, verifies
the solution and records the metrics — no other code needs touching.
"""
from __future__ import annotations

import abc
from typing import Type

from .instance import Instance
from .solution import Solution


class Algorithm(abc.ABC):
    """Base class for all benchmark algorithms.

    Subclasses must set a unique ``name`` and implement :meth:`solve`.
    ``params`` are algorithm hyper-parameters (from the YAML config);
    keep defaults sensible so ``MyAlgo()`` works out of the box.
    """

    #: unique identifier used in configs, results and plots
    name: str = None

    def __init__(self, **params):
        self.params = params

    @abc.abstractmethod
    def solve(self, instance: Instance) -> Solution:
        """Return a :class:`Solution` for ``instance``.

        Must not mutate ``instance``.  Determinism: any randomness should
        derive from ``self.params.get("seed")`` so runs are reproducible.
        """

    def __repr__(self):
        return f"{type(self).__name__}({self.params})"


def register_algorithm(cls: Type[Algorithm]) -> Type[Algorithm]:
    """Class decorator adding ``cls`` to the global component registry."""
    from .registry import registry
    if not (isinstance(cls, type) and issubclass(cls, Algorithm)):
        raise TypeError("@register_algorithm expects an Algorithm subclass")
    if not cls.name:
        raise ValueError(f"{cls.__name__} must define a non-empty `name`")
    return registry.register("algorithm", cls.name)(cls)


def get_algorithm(name: str, **params) -> Algorithm:
    """Instantiate a registered algorithm by name."""
    from .registry import registry
    _load_builtins()
    return registry.get("algorithm", name)(**params)


def list_algorithms():
    from .registry import registry
    _load_builtins()
    return registry.names("algorithm")


def _load_builtins():
    """Import bundled algorithms so their @register decorators run."""
    from .. import algorithms as _  # noqa: F401
