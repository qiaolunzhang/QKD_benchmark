"""YAML experiment configuration.

One YAML file describes a whole experiment — no environment variables, no
per-scenario entry scripts.  Example (``configs/demo.yaml``)::

    name: demo
    output: results/demo.csv
    algorithms: [greedy_sp]
    instances:
      topology: german7
      n_requests: [10, 20, 30]
      seeds: [1, 2, 3]
      num_slots: 5
      wavelengths: 2
      modules_per_node: 2
      mean_volume_kb: 100
      rate_table: fse_1540_alone
    algo_params:
      greedy_sp: {k_paths: 3}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import yaml

from ..instances.generators import make_instance


@dataclass
class ExperimentConfig:
    name: str
    algorithms: List[str]
    instances: dict
    output: str = None
    algo_params: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path) -> "ExperimentConfig":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        known = {"name", "algorithms", "instances", "output", "algo_params"}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        return cls(**raw)

    def build_instances(self):
        """Expand the instance spec into concrete Instance objects."""
        spec = dict(self.instances)
        topology = spec.pop("topology")
        n_reqs = spec.pop("n_requests")
        seeds = spec.pop("seeds", [0])
        if isinstance(n_reqs, int):
            n_reqs = [n_reqs]
        if isinstance(seeds, int):
            seeds = [seeds]
        for n in n_reqs:
            for seed in seeds:
                yield make_instance(topology=topology, n_req=n,
                                    seed=seed, **spec)
