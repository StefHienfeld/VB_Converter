"""
Quick A/B helper to compare runs with and zonder semantiek.

Requires the FastAPI backend running locally (default http://localhost:8000).
Uses the existing /api/analyze and /api/status/{job_id} endpoints.

Usage:
    python scripts/semantic_ab_check.py --policy path/to/policy.xlsx --conditions path/to/voorwaarden.pdf

Notes:
- This is a lightweight diagnostic: it fires two jobs (semantic on/off) with the same inputs,
  waits for completion, and prints the semantic-related stats from the job response.
- Install requests if not present: pip install requests
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "requests is required for this script. Install with: pip install requests"
    ) from exc


def _start_job(
    base_url: str,
    policy_path: Path,
    condition_paths: List[Path],
    use_semantic: bool,
) -> str:
    files = []

    files.append(
        (
            "policy_file",
            (
                policy_path.name,
                policy_path.read_bytes(),
                "application/octet-stream",
            ),
        )
    )

    for cond in condition_paths:
        files.append(
            (
                "conditions_files",
                (
                    cond.name,
                    cond.read_bytes(),
                    "application/octet-stream",
                ),
            )
        )

    data = {
        "cluster_accuracy": 90,
        "min_frequency": 20,
        "window_size": 100,
        "use_conditions": True,
        "use_window_limit": True,
        "use_semantic": str(use_semantic).lower(),
    }

    resp = requests.post(f"{base_url}/api/analyze", files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()["job_id"]


def _await_job(base_url: str, job_id: str, poll_interval: float = 2.0) -> dict:
    while True:
        resp = requests.get(f"{base_url}/api/status/{job_id}", timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        status = payload["status"]
        if status in {"completed", "failed"}:
            return payload
        time.sleep(poll_interval)


def run_ab_check(base_url: str, policy: Path, conditions: List[Path]) -> None:
    print(f"Starting A run (semantic ON) against {base_url}")
    job_a = _start_job(base_url, policy, conditions, use_semantic=True)
    print(f"Job A id: {job_a}")

    print("Starting B run (semantic OFF)")
    job_b = _start_job(base_url, policy, conditions, use_semantic=False)
    print(f"Job B id: {job_b}")

    result_a = _await_job(base_url, job_a)
    result_b = _await_job(base_url, job_b)

    stats_a = result_a.get("stats", {})
    stats_b = result_b.get("stats", {})

    print("\n=== Result: semantic ON ===")
    print(stats_a.get("semantic_status"))
    print("\n=== Result: semantic OFF ===")
    print(stats_b.get("semantic_status"))

    print("\nTip: Compare 'semantic_status' fields and advice distribution deltas.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Quick A/B run for semantic pipeline")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--policy", required=True, help="Path to policy CSV/Excel")
    parser.add_argument(
        "--conditions", required=True, nargs="+", help="Path(s) to voorwaarden files"
    )
    args = parser.parse_args()

    policy_path = Path(args.policy).expanduser().resolve()
    condition_paths = [Path(p).expanduser().resolve() for p in args.conditions]

    for path in [policy_path, *condition_paths]:
        if not path.exists():
            raise SystemExit(f"Bestand niet gevonden: {path}")

    run_ab_check(args.base_url, policy_path, condition_paths)


if __name__ == "__main__":
    main()

