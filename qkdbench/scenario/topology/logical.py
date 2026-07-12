"""Physical -> logical QKD topology derivation (ARCHITECTURE.md §4).

The logical QKD topology is a *derived* quantity, never stored: the
subgraph of the physical network containing only links on which the QKD
physical model can actually generate keys.  Feasibility is decided by a
:class:`~qkdbench.scenario.qkd_models.KeyGenerationModel`
(``model.feasible(length_km)``); for the finite-size tables that is
exactly the old "within tabulated reach" rule.
"""
from __future__ import annotations

from ...core.network import Network
from ...keyrate.finite_size import RateTable
from ..qkd_models import FiniteSizeTable, KeyGenerationModel, get_qkd_model


def logical_graph(network: Network, qkd_model="fse_1540_alone",
                  **model_params):
    """Return the logical QKD topology as a ``networkx`` graph.

    Args:
        network: the physical topology.
        qkd_model: a registered model name (legacy rate-table names
            ``fse_1540_alone`` / ``fse_1310_coex`` still work), a
            :class:`KeyGenerationModel` instance, or a legacy
            :class:`RateTable` instance.
        **model_params: forwarded to the model factory when
            ``qkd_model`` is a name (e.g. ``rate_kbps=50``).

    Returns:
        A copy of ``network.graph()`` with every link the model deems
        infeasible removed (all nodes are kept — a node isolated in the
        logical graph is still physical reality).  Removed links are
        listed in ``graph.graph["infeasible_links"]``.
    """
    if isinstance(qkd_model, KeyGenerationModel):
        model = qkd_model
    elif isinstance(qkd_model, RateTable):        # Phase-0 compatibility
        model = FiniteSizeTable(table=qkd_model.name)
    else:
        model = get_qkd_model(qkd_model, **model_params)
    g = network.graph().copy()
    dead = [(a, b) for a, b, d in g.edges(data=True)
            if not model.feasible(d["length_km"])]
    g.remove_edges_from(dead)
    g.graph["qkd_model"] = model.name
    g.graph["qkd_model_version"] = model.version
    # legacy key: table name for FiniteSizeTable, model name otherwise
    g.graph["rate_table"] = getattr(model, "table", model.name)
    g.graph["infeasible_links"] = dead
    return g
