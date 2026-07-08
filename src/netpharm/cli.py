"""Command-line interface.

    python -m netpharm.cli run            # full pipeline (resume-aware)
    python -m netpharm.cli run --force    # ignore cache, recompute everything
    python -m netpharm.cli step ppi       # run a single agent by name
    python -m netpharm.cli status         # show step status table
"""
from __future__ import annotations

import argparse
import sys

from .config import Config
from .db import Store
from .orchestrator import run_pipeline, run_single


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="netpharm")
    parser.add_argument("--config", default="config/config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the full pipeline")
    p_run.add_argument("--force", action="store_true", help="recompute all steps")

    p_step = sub.add_parser("step", help="run one agent by name")
    p_step.add_argument("name")

    sub.add_parser("status", help="print step status")

    args = parser.parse_args(argv)
    config = Config.load(args.config)

    if args.cmd == "run":
        result = run_pipeline(config, force=args.force)
        print("Completed:", ", ".join(result["completed"]))
    elif args.cmd == "step":
        run_single(config, args.name)
    elif args.cmd == "status":
        store = Store(config.db_path, config.output_dir)
        print(store.all_status().to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
