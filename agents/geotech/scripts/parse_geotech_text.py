#!/usr/bin/env python3
"""Create a lightweight boring-focused geotechnical summary from extracted text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BORING_PATTERN = re.compile(r"\b(B[- ]?\d+|BH[- ]?\d+|Boring\s+\d+)\b", re.IGNORECASE)
DEPTH_PATTERN = re.compile(
    r"\b(?:to|at|depth of|terminated at|termination depth[: ]*)\s*(\d+(?:\.\d+)?)\s*(ft|feet|m|meters?)\b",
    re.IGNORECASE,
)
REFUSAL_PATTERN = re.compile(r"\b(refusal|auger refusal|hard refusal|refusal on rock)\b", re.IGNORECASE)
PRELIM_PATTERN = re.compile(r"\b(preliminary geotechnical|preliminary geotech)\b", re.IGNORECASE)


def collect_lines(text: str, pattern: re.Pattern[str]) -> list[str]:
    matches: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and pattern.search(stripped):
            matches.append(stripped)
    return matches


def normalize_boring_id(raw: str) -> str:
    token = raw.strip()
    token = re.sub(r"\s+", " ", token)
    return token.upper().replace("BORING ", "BORING ")


def extract_borings(text: str) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    borings: dict[str, dict[str, object]] = {}
    findings: list[dict[str, str]] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        boring_match = BORING_PATTERN.search(stripped)
        if not boring_match:
            continue

        boring_id = normalize_boring_id(boring_match.group(1))
        depth_match = DEPTH_PATTERN.search(stripped)
        refusal_match = REFUSAL_PATTERN.search(stripped)

        if boring_id not in borings:
            borings[boring_id] = {
                "boring_id": boring_id,
                "termination_depth": None,
                "termination_depth_units": None,
                "refusal": "unclear",
                "confidence": "low",
                "source_reference": stripped,
                "notes": "Auto-extracted from text scan.",
            }

        boring = borings[boring_id]
        if depth_match:
            boring["termination_depth"] = float(depth_match.group(1))
            boring["termination_depth_units"] = depth_match.group(2)
            boring["confidence"] = "medium"
        if refusal_match:
            boring["refusal"] = "yes"
            boring["confidence"] = "medium"
        elif boring["refusal"] == "unclear":
            boring["refusal"] = "no"

        findings.append(
            {
                "topic": "borings",
                "statement": stripped,
                "confidence": "medium" if depth_match or refusal_match else "low",
                "source_reference": "text scan",
            }
        )

    return sorted(borings.values(), key=lambda item: str(item["boring_id"])), findings[:10]


def build_summary(project_id: str, text: str) -> dict[str, object]:
    borings, findings = extract_borings(text)
    refusal_observed = "yes" if any(item["refusal"] == "yes" for item in borings) else "no"
    if not borings:
        refusal_observed = "unclear"

    open_questions = []
    if not borings:
        open_questions.append("No boring identifiers were confidently detected in the extracted text.")
    elif any(item["termination_depth"] is None for item in borings):
        open_questions.append("One or more borings were detected without a clear termination depth.")
    if borings and any(item["refusal"] == "unclear" for item in borings):
        open_questions.append("Refusal language was ambiguous for one or more borings.")

    return {
        "project_id": project_id,
        "report_type": "preliminary_geotech" if PRELIM_PATTERN.search(text) else "unknown",
        "document_summary": "Auto-generated starter summary focused on preliminary geotechnical boring basics.",
        "boring_log_summary": {
            "boring_count": len(borings) if borings else None,
            "borings": borings,
            "refusal_observed": refusal_observed,
            "summary_notes": "Review against original boring logs before relying on this output.",
        },
        "findings": findings,
        "risk_flags": [],
        "foundation_considerations": [],
        "open_questions": open_questions,
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
