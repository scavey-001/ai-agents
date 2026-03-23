#!/usr/bin/env python3
"""Create a boring-focused geotechnical summary from extracted narrative text."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PRELIM_PATTERN = re.compile(r"\b(preliminary geotechnical|preliminary geotech)\b", re.IGNORECASE)
BORING_COUNT_PATTERN = re.compile(r"\badvance\s+(\d+)\s+soil borings?\b", re.IGNORECASE)
BORING_RANGE_BLOCK_PATTERN = re.compile(r"advance\s+\d+\s+soil borings?\s*\((.*?)\)", re.IGNORECASE | re.DOTALL)
SUBSTATION_REFUSAL_PATTERN = re.compile(
    r"substation borings\s*\(\s*(B-[A-Z0-9-]+)\s*&\s*(B-[A-Z0-9-]+)\s*\)\s*were advanced until practical refusal"
    r".*?approximately\s*(\d+(?:\.\d+)?)\s*feet.*?(\d+(?:\.\d+)?)\s*feet\s*BGS",
    re.IGNORECASE,
)
ARRAY_BORINGS_PATTERN = re.compile(
    r"(\d+)\s+array-area soil borings were advanced to approximately\s*(\d+(?:\.\d+)?)\s*feet"
    r".*?(practical refusal)",
    re.IGNORECASE | re.DOTALL,
)
ROCK_CORING_PATTERN = re.compile(r"\((B-[A-Z0-9-]+)\).*?rock coring", re.IGNORECASE)


def normalize_boring_id(raw: str) -> str:
    return re.sub(r"\s+", "", raw.upper())


def expand_boring_token(token: str) -> list[str]:
    cleaned = token.strip()
    if " through " not in cleaned:
        return [normalize_boring_id(cleaned)]

    start_raw, end_raw = [part.strip() for part in cleaned.split(" through ", 1)]
    start = normalize_boring_id(start_raw)
    end = normalize_boring_id(end_raw)

    match_start = re.match(r"^(.*?)(\d+)$", start)
    match_end = re.match(r"^(.*?)(\d+)$", end)
    if not match_start or not match_end:
        return [start, end]

    start_prefix, start_num = match_start.groups()
    end_prefix, end_num = match_end.groups()
    if start_prefix != end_prefix:
        return [start, end]

    width = max(len(start_num), len(end_num))
    start_int = int(start_num)
    end_int = int(end_num)
    if end_int < start_int:
        return [start, end]

    return [f"{start_prefix}{value:0{width}d}" for value in range(start_int, end_int + 1)]


def extract_boring_ids(text: str) -> list[str]:
    match = BORING_RANGE_BLOCK_PATTERN.search(text)
    if not match:
        return []

    raw_block = re.sub(r"\s+", " ", match.group(1)).strip()
    raw_block = raw_block.replace(", and ", ", ").replace(" and ", ", ")
    parts = [part.strip() for part in raw_block.split(",") if part.strip()]
    boring_ids: list[str] = []
    for part in parts:
        boring_ids.extend(expand_boring_token(part))
    seen: set[str] = set()
    ordered: list[str] = []
    for boring_id in boring_ids:
        if boring_id not in seen:
            seen.add(boring_id)
            ordered.append(boring_id)
    return ordered


def add_finding(findings: list[dict[str, str]], topic: str, statement: str, confidence: str) -> None:
    findings.append(
        {
            "topic": topic,
            "statement": statement,
            "confidence": confidence,
            "source_reference": "narrative text",
        }
    )


def build_summary(project_id: str, text: str) -> dict[str, object]:
    normalized_text = re.sub(r"\s+", " ", text)
    findings: list[dict[str, str]] = []
    open_questions: list[str] = []
    summary_notes: list[str] = []

    boring_ids = extract_boring_ids(text)
    boring_count: int | None = None
    boring_entries: list[dict[str, object]] = []

    count_match = BORING_COUNT_PATTERN.search(text)
    if count_match:
        boring_count = int(count_match.group(1))
        add_finding(findings, "boring_count", f"Report narrative states {boring_count} soil borings were advanced.", "high")
        summary_notes.append(f"Report narrative states {boring_count} total soil borings.")
    else:
        open_questions.append("Total boring count was not confidently identified from the narrative text.")

    if boring_ids:
        add_finding(
            findings,
            "boring_ids",
            f"Report narrative references boring IDs/ranges: {', '.join(boring_ids)}.",
            "medium",
        )
    else:
        open_questions.append("Boring ID list or range was not confidently extracted from the narrative text.")

    array_match = ARRAY_BORINGS_PATTERN.search(text)
    if array_match:
        array_count = int(array_match.group(1))
        array_depth = float(array_match.group(2))
        add_finding(
            findings,
            "array_borings",
            f"{array_count} array-area borings were advanced to approximately {array_depth:g} feet BGS or until practical refusal.",
            "high",
        )
        summary_notes.append(
            f"Narrative states {array_count} array-area borings were advanced to approximately {array_depth:g} feet BGS or until practical refusal."
        )
        open_questions.append(
            "Narrative gives only a general array-boring depth statement, not individual termination depths for each array boring."
        )

    substation_match = SUBSTATION_REFUSAL_PATTERN.search(normalized_text)
    if substation_match:
        boring_pair = [normalize_boring_id(substation_match.group(1)), normalize_boring_id(substation_match.group(2))]
        first_depth = float(substation_match.group(3))
        second_depth = float(substation_match.group(4))
        pairs = list(zip(boring_pair, [first_depth, second_depth]))
        for boring_id, depth in pairs:
            boring_entries.append(
                {
                    "boring_id": boring_id,
                    "termination_depth": depth,
                    "termination_depth_units": "feet BGS",
                    "refusal": "yes",
                    "confidence": "high",
                    "source_reference": "narrative text",
                    "notes": "Narrative states practical refusal was encountered.",
                }
            )
        add_finding(
            findings,
            "substation_borings",
            (
                f"Substation borings {boring_pair[0]} and {boring_pair[1]} encountered practical refusal "
                f"at approximately {first_depth:g} feet and {second_depth:g} feet BGS."
            ),
            "high",
        )
        summary_notes.append(
            f"Substation borings {boring_pair[0]} and {boring_pair[1]} reached practical refusal at approximately {first_depth:g} feet and {second_depth:g} feet BGS."
        )
    else:
        open_questions.append("Specific substation boring refusal depths were not confidently extracted.")

    rock_match = ROCK_CORING_PATTERN.search(text)
    if rock_match:
        add_finding(
            findings,
            "rock_coring",
            f"Rock coring is reported at {normalize_boring_id(rock_match.group(1))}.",
            "high",
        )

    refusal_observed = "yes" if any(entry["refusal"] == "yes" for entry in boring_entries) or array_match else "unclear"
    if not boring_entries:
        open_questions.append("Individual boring termination depths are still missing for most borings and may require attachment review.")

    return {
        "project_id": project_id,
        "report_type": "preliminary_geotech" if PRELIM_PATTERN.search(text) else "unknown",
        "document_summary": "Auto-generated summary focused on preliminary geotechnical boring basics from narrative text.",
        "boring_log_summary": {
            "boring_count": boring_count,
            "borings": boring_entries,
            "refusal_observed": refusal_observed,
            "summary_notes": " ".join(summary_notes) if summary_notes else "Review original boring logs for full per-boring detail.",
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
