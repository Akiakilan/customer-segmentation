#!/usr/bin/env python3
"""Regenerate twice with the same seed and compare CSV row counts and SHA-256 hashes."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent


def main() -> int:
    reference = Path(sys.argv[1] if len(sys.argv) > 1 else "output").resolve()
    if not (reference / "source_manifest.json").exists():
        raise SystemExit(f"Could not find source_manifest.json in: {reference}")

    manifest = json.loads((reference / "source_manifest.json").read_text(encoding="utf-8"))
    params = manifest["parameters"]
    report = {"seed": manifest["seed"], "parameters": params, "runs": [], "reference": str(reference)}
    all_ok = True

    with tempfile.TemporaryDirectory(prefix="customer_segmentation_repro_") as tmp:
        for run_number in (1, 2):
            output_dir = Path(tmp) / f"run_{run_number}"
            command = [
                sys.executable,
                str(SCRIPT_DIR / "generate_data.py"),
                "--seed", str(manifest["seed"]),
                "--n-customers", str(params["n_customers"]),
                "--n-orders", str(params["n_orders"]),
                "--n-events", str(params["n_events"]),
                "--out", str(output_dir),
                "--no-db", "--no-json",
            ]
            subprocess.run(command, check=True, cwd=PROJECT_DIR, stdout=subprocess.DEVNULL)
            regenerated = json.loads((output_dir / "source_manifest.json").read_text(encoding="utf-8"))
            differences = [
                table for table, expected in manifest["files"].items()
                if table not in regenerated["files"]
                or regenerated["files"][table]["rows"] != expected["rows"]
                or regenerated["files"][table]["sha256"] != expected["sha256"]
            ]
            identical = not differences
            all_ok &= identical
            report["runs"].append({
                "run": run_number,
                "identical_to_reference": identical,
                "differing_files": differences,
            })

    report["all_runs_identical"] = all_ok
    (reference / "reproducibility_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Reference: {reference}")
    print(f"Reproducible: {all_ok}")
    for run in report["runs"]:
        print(f"Run {run['run']}: identical={run['identical_to_reference']}; differences={run['differing_files']}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
