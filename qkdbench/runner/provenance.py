"""Reproducibility metadata for a benchmark run.

Every run writes a ``meta.json`` next to its results capturing exactly
what produced them: the config, the instance fingerprints, the code
commit, and the software/OS environment.  This is the difference between
"here is a CSV" and "here is a CSV anyone can regenerate" — the
reproducibility contract of a benchmark (ARCHITECTURE.md §10).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from typing import List


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _dep_versions() -> dict:
    versions = {}
    for pkg in ("networkx", "matplotlib", "pyyaml", "pulp"):
        try:
            mod = __import__("yaml" if pkg == "pyyaml" else pkg)
            versions[pkg] = getattr(mod, "__version__", "unknown")
        except Exception:
            versions[pkg] = "not installed"
    return versions


def config_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


def build_metadata(experiment: str, config: dict, instances,
                   timestamp: str = None) -> dict:
    """Assemble the reproducibility record for a run.

    ``timestamp`` is passed in (not read from the clock) so callers stay
    in control of determinism; pass ``None`` to omit it.
    """
    import qkdbench

    fingerprints = {inst.name: inst.fingerprint() for inst in instances}
    return {
        "experiment": experiment,
        "timestamp": timestamp,
        "config_hash": config_hash(config),
        "config": config,
        "qkdbench_version": qkdbench.__version__,
        "code_commit": _git_commit(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dependencies": _dep_versions(),
        "instance_fingerprints": fingerprints,
        "num_instances": len(fingerprints),
    }


def write_metadata(path, metadata: dict) -> None:
    with open(path, "w") as fh:
        json.dump(metadata, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
