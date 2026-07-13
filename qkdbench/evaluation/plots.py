"""Unified plotting for benchmark results.

One function draws the standard benchmark figure — a metric versus a sweep
variable, one line per algorithm, with 95% confidence-interval error bars
— straight from a results CSV.  Keeping plotting in the framework (rather
than a pile of per-paper scripts) is what makes every figure reproducible
from ``qkdbench run`` output.
"""
from __future__ import annotations

from .aggregate import aggregate_by


def plot_metric(csv_path, metric: str, out_path=None, xlabel: str = "load",
                ylabel: str = None, title: str = None,
                x_from_instance=None, algorithms=None):
    """Plot ``metric`` vs. the sweep variable with per-algorithm CI bands.

    Args:
        csv_path: a results CSV written by the runner.
        metric: column to plot (e.g. ``"served"``, ``"acceptance_ratio"``).
        out_path: file to save (``.pdf``/``.png``); if ``None`` the figure
            is returned without saving.
        algorithms: optional subset/order of algorithm names to draw.

    Returns the matplotlib ``Figure``.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curves = aggregate_by(csv_path, metric, x_from_instance=x_from_instance)
    names = algorithms or sorted(curves)

    fig, ax = plt.subplots(figsize=(5.0, 3.4))
    for name in names:
        if name not in curves:
            continue
        xs = sorted(curves[name])
        ys = [curves[name][x].mean for x in xs]
        errs = [curves[name][x].ci95 for x in xs]
        ax.errorbar(xs, ys, yerr=errs, marker="o", capsize=3, label=name)

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel or metric)
    if title:
        ax.set_title(title)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path)
    return fig
