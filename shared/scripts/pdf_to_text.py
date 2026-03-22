#!/usr/bin/env python3
"""Extract text from a PDF into stdout or a target file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def extract_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: pypdf. Install it in the active environment before running this script."
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a PDF file.")
    parser.add_argument("pdf_path", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output text file path. Defaults to stdout.",
    )
    args = parser.parse_args()

    text = extract_text(args.pdf_path)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
