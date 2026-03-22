#!/usr/bin/env python3
"""Generate a simple file inventory for a project tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_inventory(root: Path) -> list[dict[str, object]]:
    inventory = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        stat = path.stat()
        inventory.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": stat.st_size,
            }
        )
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory files under a directory.")
    parser.add_argument("root", type=Path, help="Directory to inventory.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to stdout.",
    )
    args = parser.parse_args()

    payload = {
        "root": str(args.root.resolve()),
        "files": build_inventory(args.root),
    }
    content = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
