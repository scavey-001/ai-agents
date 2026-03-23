#!/usr/bin/env python3
"""Extract per-page text from a PDF using pdftotext."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def extract_pages(
    pdf_path: Path,
    first_page: int | None,
    last_page: int | None,
) -> list[dict[str, object]]:
    pdftotext_path = shutil.which("pdftotext")
    if not pdftotext_path:
        raise SystemExit("Missing dependency: pdftotext is not installed or not on PATH.")

    cmd = [pdftotext_path]
    if first_page is not None:
        cmd.extend(["-f", str(first_page)])
    if last_page is not None:
        cmd.extend(["-l", str(last_page)])
    cmd.extend([str(pdf_path), "-"])

    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw_pages = completed.stdout.split("\f")

    pages: list[dict[str, object]] = []
    page_number = first_page or 1
    for raw_page in raw_pages:
        text = raw_page.strip()
        if not text:
            continue
        pages.append({"page_number": page_number, "text": text})
        page_number += 1
    return pages


def pages_to_text(pages: list[dict[str, object]]) -> str:
    chunks: list[str] = []
    for page in pages:
        chunks.append(f"--- Page {page['page_number']} ---")
        chunks.append(str(page["text"]))
    return "\n\n".join(chunks).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract per-page text from a PDF using pdftotext.")
    parser.add_argument("pdf_path", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output text file path. Defaults to stdout.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON output path for page-wise extracted text.",
    )
    parser.add_argument(
        "--first-page",
        type=int,
        help="Optional first page to extract, using 1-based page numbering.",
    )
    parser.add_argument(
        "--last-page",
        type=int,
        help="Optional last page to extract, using 1-based page numbering.",
    )
    args = parser.parse_args()

    pages = extract_pages(
        args.pdf_path,
        first_page=args.first_page,
        last_page=args.last_page,
    )
    text = pages_to_text(pages)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")

    if args.json_output:
        args.json_output.write_text(json.dumps(pages, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
