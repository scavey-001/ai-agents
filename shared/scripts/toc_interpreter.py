#!/usr/bin/env python3
"""Interpret TOC sections and recommend a narrative extraction endpoint."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PAGE_MARKER = re.compile(r"^--- Page (\d+) ---$", re.MULTILINE)
TABLE_OF_CONTENTS_MARKER = re.compile(r"\btable of contents\b", re.IGNORECASE)
TOC_ENTRY_PATTERN = re.compile(
    r"(?:(\d+(?:\.\d+)*)\s+)?([A-Z][A-Za-z0-9&/,\-()' ]{2,}?)\s*\.{2,}\s*(\d+)",
    re.IGNORECASE,
)
NON_NARRATIVE_TITLE_PATTERNS = [
    re.compile(r"\bappendix\b", re.IGNORECASE),
    re.compile(r"\bappendices\b", re.IGNORECASE),
    re.compile(r"\bexhibits?\b", re.IGNORECASE),
    re.compile(r"\battachments?\b", re.IGNORECASE),
    re.compile(r"\bboring logs?\b", re.IGNORECASE),
    re.compile(r"\bfigures?\b", re.IGNORECASE),
    re.compile(r"\bplates?\b", re.IGNORECASE),
    re.compile(r"\breferences?\b", re.IGNORECASE),
]


def split_pages(text: str) -> list[tuple[int, str]]:
    matches = list(PAGE_MARKER.finditer(text))
    if not matches:
        return [(1, text.strip())]

    pages: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((page_number, text[start:end].strip()))
    return pages


def parse_toc_entries(page_text: str) -> list[dict[str, object]]:
    normalized = re.sub(r"\s+", " ", page_text)
    normalized = re.sub(r"^\s*Table of Contents\s*", "", normalized, flags=re.IGNORECASE)
    entries: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()

    for match in TOC_ENTRY_PATTERN.finditer(normalized):
        section_number = match.group(1) or None
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        report_page = int(match.group(3))
        key = (title.lower(), report_page)
        if key in seen:
            continue
        seen.add(key)

        entries.append(
            {
                "section_number": section_number,
                "title": title,
                "report_page": report_page,
            }
        )
    return entries


def is_non_narrative_title(title: str) -> bool:
    return any(pattern.search(title) for pattern in NON_NARRATIVE_TITLE_PATTERNS)


def classify_section_type(title: str) -> str:
    if is_non_narrative_title(title):
        return "non_narrative"
    return "narrative"


def is_top_level_entry(entry: dict[str, object]) -> bool:
    section_number = entry.get("section_number")
    title = str(entry.get("title", "")).strip()
    if not title or title.lower().startswith("table of contents"):
        return False
    if isinstance(section_number, str) and section_number:
        return "." not in section_number
    if re.match(r"^[A-Z][A-Za-z/&,\-()' ]+$", title):
        return True
    return False


def find_toc_page(pages: list[tuple[int, str]]) -> tuple[int | None, list[dict[str, object]]]:
    for page_number, page_text in pages:
        if TABLE_OF_CONTENTS_MARKER.search(page_text):
            return page_number, parse_toc_entries(page_text)
    return None, []


def choose_narrative_end_section(
    toc_entries: list[dict[str, object]],
) -> tuple[dict[str, object] | None, str, list[dict[str, object]]]:
    if not toc_entries:
        return None, "no_toc_entries", []

    top_level_sections = [entry for entry in toc_entries if is_top_level_entry(entry)]
    if not top_level_sections:
        top_level_sections = toc_entries

    for entry in reversed(top_level_sections):
        title = str(entry["title"])
        if is_non_narrative_title(title):
            continue
        return entry, "last_top_level_narrative_section", top_level_sections

    return None, "all_top_level_sections_non_narrative", top_level_sections


def interpret_toc(text: str) -> dict[str, object]:
    pages = split_pages(text)
    toc_page_pdf, toc_entries = find_toc_page(pages)

    if toc_page_pdf is None:
        return {
            "version": "1.0",
            "strategy": "toc_not_found",
            "toc_page_pdf": None,
            "toc_entries": [],
            "top_level_sections": [],
            "narrative_end_recommendation": None,
            "total_pdf_pages_seen": len(pages),
        }

    enriched_entries: list[dict[str, object]] = []
    for entry in toc_entries:
        section_title = str(entry["title"])
        enriched_entries.append(
            {
                **entry,
                "section_type": classify_section_type(section_title),
            }
        )

    selected, strategy, top_level_sections = choose_narrative_end_section(enriched_entries)
    recommendation: dict[str, object] | None = None
    if selected is not None:
        report_page = int(selected["report_page"])
        first_narrative_pdf_page = min(toc_page_pdf + 1, len(pages))
        recommended_pdf_page = min(first_narrative_pdf_page + report_page - 1, len(pages))
        recommendation = {
            "report_page": report_page,
            "pdf_page": recommended_pdf_page,
            "section_number": selected.get("section_number"),
            "section_title": selected.get("title"),
            "reason": strategy,
        }

    return {
        "version": "1.0",
        "strategy": f"deterministic:{strategy}",
        "toc_page_pdf": toc_page_pdf,
        "toc_entries": enriched_entries,
        "top_level_sections": top_level_sections,
        "narrative_end_recommendation": recommendation,
        "total_pdf_pages_seen": len(pages),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpret TOC and return a narrative endpoint recommendation.")
    parser.add_argument("input_text", type=Path, help="Path to extracted text with page markers.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output JSON path. Defaults to stdout.",
    )
    args = parser.parse_args()

    text = args.input_text.read_text(encoding="utf-8")
    payload = interpret_toc(text)
    content = json.dumps(payload, indent=2) + "\n"

    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
