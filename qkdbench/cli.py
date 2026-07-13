"""Command-line interface.

    qkdbench run -c configs/demo.yaml     # run an experiment
    qkdbench list-algorithms              # what is registered
    qkdbench list-topologies
"""
from __future__ import annotations

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="qkdbench",
        description="Benchmark for QKD network resource optimization")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run an experiment from a YAML config")
    p_run.add_argument("-c", "--config", required=True)
    p_run.add_argument("-o", "--output",
                       help="override the CSV output path in the config")
    p_run.add_argument("-q", "--quiet", action="store_true")

    sub.add_parser("list-algorithms", help="registered algorithms")
    sub.add_parser("list-topologies", help="built-in topologies")

    args = parser.parse_args(argv)

    if args.command == "list-algorithms":
        from .core.algorithm import list_algorithms
        for name in list_algorithms():
            print(name)
    elif args.command == "list-topologies":
        from .topology.builtin import TOPOLOGIES
        for name in sorted(TOPOLOGIES):
            print(name)
    elif args.command == "run":
        from .runner.benchmark import run_benchmark
        from .runner.config import ExperimentConfig
        cfg = ExperimentConfig.from_yaml(args.config)
        csv_path = args.output or cfg.output
        instances = list(cfg.build_instances())    # materialize once
        results = run_benchmark(instances, cfg.algorithms,
                                algo_params=cfg.algo_params,
                                csv_path=csv_path,
                                verbose=not args.quiet)
        ok = sum(r.status == "ok" for r in results)
        msg = f"\n{cfg.name}: {ok}/{len(results)} runs ok"
        if csv_path:
            # write reproducibility metadata next to the results CSV
            from pathlib import Path
            from .runner.provenance import build_metadata, write_metadata
            meta_path = Path(csv_path).with_name(
                Path(csv_path).stem + ".meta.json")
            meta = build_metadata(cfg.name, {
                "algorithms": cfg.algorithms,
                "instances": cfg.instances,
                "algo_params": cfg.algo_params}, instances)
            write_metadata(meta_path, meta)
            msg += f", results -> {csv_path}, metadata -> {meta_path}"
        print(msg)


if __name__ == "__main__":
    main()
