#!/usr/bin/env python3
"""Detect the narrative section of a report using TOC-first logic with heuristic fallback."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from toc_interpreter import interpret_toc_entries


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
]
HEURISTIC_END_MARKERS = [
    re.compile(r"\bappendix\b", re.IGNORECASE),
    re.compile(r"\bappendices\b", re.IGNORECASE),
    re.compile(r"\bexhibits?\b", re.IGNORECASE),
    re.compile(r"\bboring logs?\b", re.IGNORECASE),
    re.compile(r"\bfigures?\b", re.IGNORECASE),
    re.compile(r"\bplates?\b", re.IGNORECASE),
    re.compile(r"\battachments?\b", re.IGNORECASE),
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


def choose_narrative_end_report_page(
    toc_entries: list[dict[str, object]]
) -> tuple[int | None, str, dict[str, object] | None, list[dict[str, object]]]:
    if not toc_entries:
        return None, "no_toc_entries", None, []

    top_level_sections = [entry for entry in toc_entries if is_top_level_entry(entry)]
    if not top_level_sections:
        top_level_sections = toc_entries

    for entry in reversed(top_level_sections):
        title = str(entry["title"])
        if is_non_narrative_title(title):
            continue
        return int(entry["report_page"]), "last_top_level_narrative_section", entry, top_level_sections

    return None, "all_top_level_sections_non_narrative", None, top_level_sections


def detect_with_toc(
    pages: list[tuple[int, str]],
    use_llm_toc: bool = False,
    llm_model: str = "gpt-4.1-mini",
) -> dict[str, object] | None:
    toc_page_number: int | None = None
    toc_entries: list[dict[str, object]] = []

    for page_number, page_text in pages:
        if TABLE_OF_CONTENTS_MARKER.search(page_text):
            toc_page_number = page_number
            toc_entries = parse_toc_entries(page_text)
            break

    if toc_page_number is None:
        return None

    interpreter_result: dict[str, Any] = interpret_toc_entries(
        toc_entries=toc_entries,
        use_llm=use_llm_toc,
        llm_model=llm_model,
    )

    end_report_page = interpreter_result.get("recommended_narrative_end_report_page")
    if not isinstance(end_report_page, int):
        end_report_page = None
    selected_section = None
    selected_title = interpreter_result.get("recommended_narrative_end_section_title")
    if isinstance(selected_title, str):
        for entry in toc_entries:
            if str(entry.get("title", "")).strip() == selected_title.strip():
                selected_section = entry
                break

    if end_report_page is None:
        end_report_page, strategy, selected_section, top_level_sections = choose_narrative_end_report_page(toc_entries)
    else:
        strategy = "llm_toc_interpreter" if use_llm_toc else "deterministic_toc_interpreter"
        top_level_sections = [entry for entry in toc_entries if is_top_level_entry(entry)]

    if end_report_page is None:
        return {
            "strategy": "toc_failed",
            "toc_page": toc_page_number,
            "toc_entries": toc_entries,
            "top_level_sections": top_level_sections,
            "toc_interpreter": interpreter_result,
        }

    first_narrative_pdf_page = min(toc_page_number + 1, len(pages))
    detected_end_page = min(first_narrative_pdf_page + end_report_page - 1, len(pages))

    narrative_text_parts = []
    for page_number, page_text in pages:
        if page_number <= detected_end_page:
            narrative_text_parts.append(f"--- Page {page_number} ---\n{page_text}".strip())

    return {
        "strategy": f"toc:{strategy}",
        "toc_page": toc_page_number,
        "toc_entries": toc_entries,
        "top_level_sections": top_level_sections,
        "selected_end_section": selected_section,
        "toc_interpreter": interpreter_result,
        "detected_narrative_end_page": detected_end_page,
        "detected_narrative_end_report_page": end_report_page,
        "total_pages_seen": len(pages),
        "narrative_text": "\n\n".join(narrative_text_parts).strip(),
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


def detect_narrative_end(
    text: str,
    use_llm_toc: bool = False,
    llm_model: str = "gpt-4.1-mini",
) -> dict[str, object]:
    pages = split_pages(text)
    toc_result = detect_with_toc(
        pages,
        use_llm_toc=use_llm_toc,
        llm_model=llm_model,
    )
    if toc_result and toc_result.get("detected_narrative_end_page") is not None:
        return toc_result
    heuristic_result = detect_with_heuristics(pages)
    if toc_result:
        heuristic_result["toc_page"] = toc_result.get("toc_page")
        heuristic_result["toc_entries"] = toc_result.get("toc_entries", [])
        heuristic_result["toc_failure"] = toc_result.get("strategy")
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
    parser.add_argument(
        "--use-llm-toc",
        action="store_true",
        help="Enable LLM-backed TOC interpretation if OPENAI_API_KEY is available.",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-4.1-mini",
        help="Model name to use for LLM TOC interpretation.",
    )
    args = parser.parse_args()

    text = args.input_text.read_text(encoding="utf-8")
    result = detect_narrative_end(
        text,
        use_llm_toc=args.use_llm_toc,
        llm_model=args.llm_model,
    )

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
