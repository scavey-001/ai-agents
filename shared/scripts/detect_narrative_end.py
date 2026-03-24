#!/usr/bin/env python3
"""Detect the narrative section of a report using TOC-first logic with heuristic fallback."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from toc_interpreter import interpret_toc, split_pages


HEURISTIC_END_MARKERS = [
    re.compile(r"\bappendix\b", re.IGNORECASE),
    re.compile(r"\bappendices\b", re.IGNORECASE),
    re.compile(r"\bexhibits?\b", re.IGNORECASE),
    re.compile(r"\bboring logs?\b", re.IGNORECASE),
    re.compile(r"\bfigures?\b", re.IGNORECASE),
    re.compile(r"\bplates?\b", re.IGNORECASE),
    re.compile(r"\battachments?\b", re.IGNORECASE),
]


def detect_with_toc(pages: list[tuple[int, str]], full_text: str) -> dict[str, object] | None:
    toc_result = interpret_toc(full_text)
    recommendation = toc_result.get("narrative_end_recommendation")
    if not isinstance(recommendation, dict):
        return {
            "strategy": "toc_failed",
            "toc_page": toc_result.get("toc_page_pdf"),
            "toc_entries": toc_result.get("toc_entries", []),
            "top_level_sections": toc_result.get("top_level_sections", []),
            "toc_strategy": toc_result.get("strategy"),
        }

    detected_end_page = int(recommendation["pdf_page"])
    end_report_page = int(recommendation["report_page"])

    narrative_text_parts = []
    for page_number, page_text in pages:
        if page_number <= detected_end_page:
            narrative_text_parts.append(f"--- Page {page_number} ---\n{page_text}".strip())

    selected_end_section = {
        "section_number": recommendation.get("section_number"),
        "title": recommendation.get("section_title"),
        "report_page": end_report_page,
    }

    return {
        "strategy": f"toc:{recommendation.get('reason')}",
        "toc_page": toc_result.get("toc_page_pdf"),
        "toc_entries": toc_result.get("toc_entries", []),
        "top_level_sections": toc_result.get("top_level_sections", []),
        "selected_end_section": selected_end_section,
        "detected_narrative_end_page": detected_end_page,
        "detected_narrative_end_report_page": end_report_page,
        "total_pages_seen": len(pages),
        "narrative_text": "\n\n".join(narrative_text_parts).strip(),
        "toc_interpreter": toc_result,
    }


def detect_with_heuristics(pages: list[tuple[int, str]]) -> dict[str, object]:
    detected_end_page: int | None = None
    marker_hits: list[dict[str, object]] = []

    for page_number, page_text in pages:
        if page_number < 4:
            continue
        first_lines = "\n".join(page_text.splitlines()[:25])
        for pattern in HEURISTIC_END_MARKERS:
            if pattern.search(first_lines):
                marker_hits.append({"page_number": page_number, "marker": pattern.pattern})
                if detected_end_page is None:
                    detected_end_page = max(1, page_number - 1)
                break

    if detected_end_page is None:
        detected_end_page = min(20, len(pages))

    narrative_text_parts = []
    for page_number, page_text in pages:
        if page_number <= detected_end_page:
            narrative_text_parts.append(f"--- Page {page_number} ---\n{page_text}".strip())

    return {
        "strategy": "heuristic",
        "detected_narrative_end_page": detected_end_page,
        "total_pages_seen": len(pages),
        "marker_hits": marker_hits,
        "narrative_text": "\n\n".join(narrative_text_parts).strip(),
    }


def detect_narrative_end(text: str) -> dict[str, object]:
    pages = split_pages(text)
    toc_result = detect_with_toc(pages, text)
    if toc_result and toc_result.get("detected_narrative_end_page") is not None:
        return toc_result

    heuristic_result = detect_with_heuristics(pages)
    if toc_result:
        heuristic_result["toc_page"] = toc_result.get("toc_page")
        heuristic_result["toc_entries"] = toc_result.get("toc_entries", [])
        heuristic_result["toc_failure"] = toc_result.get("strategy")
        heuristic_result["toc_interpreter"] = toc_result.get("toc_interpreter")
    return heuristic_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect the likely narrative cutoff in extracted report text.")
    parser.add_argument("input_text", type=Path, help="Path to extracted text with page markers.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output text path for the detected narrative section.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional output JSON path for the detection metadata.",
    )
    args = parser.parse_args()

    text = args.input_text.read_text(encoding="utf-8")
    result = detect_narrative_end(text)

    if args.output:
        args.output.write_text(str(result["narrative_text"]) + "\n", encoding="utf-8")
    else:
        sys.stdout.write(str(result["narrative_text"]) + "\n")

    if args.json_output:
        payload = dict(result)
        payload.pop("narrative_text", None)
        args.json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
