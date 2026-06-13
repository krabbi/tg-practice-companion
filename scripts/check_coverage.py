"""Per-file coverage gate for the bot/ package.

Parses coverage.json (produced by --cov-report=json) and fails with a non-zero
exit code if ANY bot/ file is below the threshold.

Usage:
    python scripts/check_coverage.py            # default threshold 80
    python scripts/check_coverage.py --threshold 90
    python scripts/check_coverage.py --json-file path/to/coverage.json
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-file coverage gate")
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Minimum per-file coverage percent (default: 80)",
    )
    parser.add_argument(
        "--json-file",
        default="coverage.json",
        help="Path to coverage.json produced by pytest-cov --cov-report=json",
    )
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"ERROR: coverage report not found at {json_path}", file=sys.stderr)
        print("       Run: pytest --cov=bot --cov-report=json first", file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text())
    files = data.get("files", {})

    failing: list[tuple[str, float]] = []

    for file_path, info in files.items():
        # Only enforce the gate on bot/ source files; skip __init__.py (always 100%)
        norm = file_path.replace("\\", "/")
        if not norm.startswith("bot/"):
            continue
        if norm.endswith("__init__.py"):
            continue

        pct: float = info["summary"]["percent_covered"]
        if pct < args.threshold:
            failing.append((norm, pct))

    if failing:
        print(
            f"FAIL — {len(failing)} bot/ file(s) below {args.threshold:.0f}% coverage:\n",
            file=sys.stderr,
        )
        for path, pct in sorted(failing):
            print(f"  {pct:5.1f}%  {path}", file=sys.stderr)
        print(file=sys.stderr)
        return 1

    # Print a short summary of all bot/ files
    covered = [
        (file_path.replace("\\", "/"), info["summary"]["percent_covered"])
        for file_path, info in files.items()
        if file_path.replace("\\", "/").startswith("bot/")
        and not file_path.replace("\\", "/").endswith("__init__.py")
    ]
    print(f"OK — all {len(covered)} bot/ files are >= {args.threshold:.0f}% coverage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
