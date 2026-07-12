"""qkdbench — a benchmark framework for QKD network resource optimization.

Quickstart::

    from qkdbench import make_instance, get_algorithm, evaluate

    inst = make_instance("german7", n_req=20, seed=1)
    result = evaluate(inst, get_algorithm("greedy_sp"))
    print(result.served, "/", result.total_requests)

Adding an algorithm::

    from qkdbench import Algorithm, register_algorithm, Solution

    @register_algorithm
    class MyAlgo(Algorithm):
        name = "my_algo"
        def solve(self, instance):
            return Solution(algorithm=self.name, assignments=[...])
"""
from .core.network import Network, Node, Link, edge_key
from .core.demand import Demand, Request
from .core.instance import Instance
from .core.solution import Assignment, Solution
from .core.result import Result
from .core.algorithm import (Algorithm, register_algorithm,
                             get_algorithm, list_algorithms)
from .core.verifier import verify
from .keyrate.finite_size import get_rate_table, available_tables
from .topology.builtin import get_topology
from .scenario.qkd_models import (KeyGenerationModel, KeyGenResult,
                                  get_qkd_model)
from .scenario.topology import (TopologyProvider, build_topology,
                                logical_graph)
from .problems import (Problem, DecisionModule, ConstraintModule,
                       ObjectiveModule, get_problem, list_problems)
from .instances.generators import make_instance, uniform_requests
from .runner.benchmark import evaluate, run_benchmark
from .runner.config import ExperimentConfig

__version__ = "0.1.0"

__all__ = [
    "Instance", "Network", "Node", "Link", "Demand", "Request", "edge_key",
    "Assignment", "Solution", "Result",
    "Algorithm", "register_algorithm", "get_algorithm", "list_algorithms",
    "verify", "get_rate_table", "available_tables", "get_topology",
    "KeyGenerationModel", "KeyGenResult", "get_qkd_model",
    "TopologyProvider", "build_topology", "logical_graph",
    "Problem", "DecisionModule", "ConstraintModule", "ObjectiveModule",
    "get_problem", "list_problems",
    "make_instance", "uniform_requests",
    "evaluate", "run_benchmark", "ExperimentConfig",
]
