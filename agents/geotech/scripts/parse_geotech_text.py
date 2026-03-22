#!/usr/bin/env python3
"""Create a lightweight geotechnical summary skeleton from extracted text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BORING_PATTERN = re.compile(r"\b(B[- ]?\d+|BH[- ]?\d+|Boring\s+\d+)\b", re.IGNORECASE)
GROUNDWATER_PATTERN = re.compile(r"\bgroundwater\b", re.IGNORECASE)
FOUNDATION_PATTERN = re.compile(r"\bfoundation\b", re.IGNORECASE)


def collect_sentences(text: str, pattern: re.Pattern[str]) -> list[str]:
    matches = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and pattern.search(stripped):
            matches.append(stripped)
    return matches


def build_summary(project_id: str, text: str) -> dict[str, object]:
    boring_hits = collect_sentences(text, BORING_PATTERN)
    groundwater_hits = collect_sentences(text, GROUNDWATER_PATTERN)
    foundation_hits = collect_sentences(text, FOUNDATION_PATTERN)

    findings = []
    for sentence in boring_hits[:5]:
        findings.append(
            {
                "topic": "borings",
                "statement": sentence,
                "confidence": "medium",
                "source_reference": "text scan",
            }
        )
    for sentence in groundwater_hits[:5]:
        findings.append(
            {
                "topic": "groundwater",
                "statement": sentence,
                "confidence": "medium",
                "source_reference": "text scan",
            }
        )

    return {
        "project_id": project_id,
        "document_summary": "Auto-generated starter summary from extracted geotechnical text.",
        "findings": findings,
        "risk_flags": [],
        "foundation_considerations": foundation_hits[:5],
        "open_questions": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse extracted geotechnical text into a starter JSON summary.")
    parser.add_argument("project_id", help="Project identifier.")
    parser.add_argument("input_text", type=Path, help="Path to extracted text.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output JSON path. Defaults to stdout.",
    )
    args = parser.parse_args()

    text = args.input_text.read_text(encoding="utf-8")
    payload = build_summary(args.project_id, text)
    content = json.dumps(payload, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
