#!/usr/bin/env python3
"""Import/register rollout Jobs in-process using the target Nautobot environment.

Run with the Nautobot worker's Python, for example:
  python /path/to/blog-sandbox/tools/validate_gc_rollout_import.py

Does not execute Jobs, persist registration, enqueue tasks or connect to devices.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Optional Nautobot configuration path; defaults to the worker's configuration")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "jobs/gc_rollout")
    args = parser.parse_args()
    import nautobot
    nautobot.setup(args.config)
    spec = importlib.util.spec_from_file_location("rollout_runtime_validation", args.source / "__init__.py",
                                                  submodule_search_locations=[str(args.source)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    from nautobot.apps.jobs import register_jobs
    jobs = [module.PrepareGCRollout, module.ExecuteGCRollout, module.CancelGCRollout, module.ReconcileGCRollout]
    register_jobs(*jobs)
    for cls in jobs:
        cls()
        print(json.dumps({"class": cls.__name__, "variables": list(cls._get_vars()),
                          "singleton": cls.is_singleton, "soft_time_limit": cls.soft_time_limit}))
    print("Imports and in-process registration passed. No Jobs were executed or enqueued.")


if __name__ == "__main__":
    main()
