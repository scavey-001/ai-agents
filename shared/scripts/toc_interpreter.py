#!/usr/bin/env python3
"""Interpret TOC sections and recommend a narrative extraction endpoint."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


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
OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
TOC_CONTEXT_PAGE_LIMIT = 3
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = REPO_ROOT / ".env"


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


def merge_toc_entries(*entry_lists: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen: set[tuple[str | None, str, int]] = set()
    for entry_list in entry_lists:
        for entry in entry_list:
            section_number = entry.get("section_number")
            title = str(entry.get("title", "")).strip()
            report_page = int(entry["report_page"])
            key = (str(section_number) if section_number is not None else None, title.lower(), report_page)
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "section_number": section_number,
                    "title": title,
                    "report_page": report_page,
                }
            )
    return merged


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


def find_toc_pages(
    pages: list[tuple[int, str]]
) -> tuple[int | None, list[tuple[int, str]], list[dict[str, object]]]:
    toc_page_index: int | None = None
    toc_pages: list[tuple[int, str]] = []
    for index, (page_number, page_text) in enumerate(pages):
        if TABLE_OF_CONTENTS_MARKER.search(page_text):
            toc_page_index = index
            toc_pages.append((page_number, page_text))
            break

    if toc_page_index is None:
        return None, [], []

    toc_entries = parse_toc_entries(toc_pages[0][1])
    pages_without_entries = 0
    for page_number, page_text in pages[toc_page_index + 1 : toc_page_index + TOC_CONTEXT_PAGE_LIMIT]:
        page_entries = parse_toc_entries(page_text)
        if not page_entries:
            pages_without_entries += 1
            if toc_entries and pages_without_entries >= 1:
                break
            continue
        toc_pages.append((page_number, page_text))
        toc_entries = merge_toc_entries(toc_entries, page_entries)
        pages_without_entries = 0

    return toc_pages[0][0], toc_pages, toc_entries


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


def load_dotenv(env_path: Path = DEFAULT_ENV_PATH) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def build_final_payload(
    *,
    pages: list[tuple[int, str]],
    toc_page_pdf: int | None,
    toc_entries: list[dict[str, object]],
    top_level_sections: list[dict[str, object]],
    selected: dict[str, object] | None,
    strategy: str,
) -> dict[str, object]:
    recommendation: dict[str, object] | None = None
    if toc_page_pdf is not None and selected is not None:
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
        "version": "1.1",
        "strategy": strategy,
        "toc_page_pdf": toc_page_pdf,
        "toc_entries": toc_entries,
        "top_level_sections": top_level_sections,
        "narrative_end_recommendation": recommendation,
        "total_pdf_pages_seen": len(pages),
    }


def interpret_toc_deterministic(text: str) -> dict[str, object]:
    pages = split_pages(text)
    toc_page_pdf, _, toc_entries = find_toc_pages(pages)

    if toc_page_pdf is None:
        return build_final_payload(
            pages=pages,
            toc_page_pdf=None,
            toc_entries=[],
            top_level_sections=[],
            selected=None,
            strategy="deterministic:toc_not_found",
        )

    enriched_entries: list[dict[str, object]] = []
    for entry in toc_entries:
        section_title = str(entry["title"])
        enriched_entries.append(
            {
                **entry,
                "section_type": classify_section_type(section_title),
            }
        )

    selected, selection_strategy, top_level_sections = choose_narrative_end_section(enriched_entries)
    return build_final_payload(
        pages=pages,
        toc_page_pdf=toc_page_pdf,
        toc_entries=enriched_entries,
        top_level_sections=top_level_sections,
        selected=selected,
        strategy=f"deterministic:{selection_strategy}",
    )


def build_llm_input(
    toc_pages: list[tuple[int, str]],
    parsed_entries: list[dict[str, object]],
) -> str:
    toc_page_blocks = [
        f"--- PDF Page {page_number} ---\n{page_text}".strip() for page_number, page_text in toc_pages
    ]
    return (
        "TOC source pages:\n"
        + "\n\n".join(toc_page_blocks)
        + "\n\nDeterministically parsed TOC entries:\n"
        + json.dumps(parsed_entries, indent=2)
    )


def openai_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "strategy",
            "toc_entries",
            "top_level_sections",
            "narrative_end_recommendation",
        ],
        "properties": {
            "strategy": {"type": "string"},
            "toc_entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section_number", "title", "report_page", "section_type"],
                    "properties": {
                        "section_number": {"type": ["string", "null"]},
                        "title": {"type": "string"},
                        "report_page": {"type": "integer", "minimum": 1},
                        "section_type": {"type": "string", "enum": ["narrative", "non_narrative"]},
                    },
                    "additionalProperties": False,
                },
            },
            "top_level_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["section_number", "title", "report_page", "section_type"],
                    "properties": {
                        "section_number": {"type": ["string", "null"]},
                        "title": {"type": "string"},
                        "report_page": {"type": "integer", "minimum": 1},
                        "section_type": {"type": "string", "enum": ["narrative", "non_narrative"]},
                    },
                    "additionalProperties": False,
                },
            },
            "narrative_end_recommendation": {
                "type": ["object", "null"],
                "required": ["report_page", "section_number", "section_title", "reason"],
                "properties": {
                    "report_page": {"type": "integer", "minimum": 1},
                    "section_number": {"type": ["string", "null"]},
                    "section_title": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def call_openai_toc_interpreter(
    *,
    text: str,
    pages: list[tuple[int, str]],
    toc_page_pdf: int,
    toc_pages: list[tuple[int, str]],
    parsed_entries: list[dict[str, object]],
    model: str,
    timeout_seconds: int,
) -> dict[str, object]:
    prompt = (
        "You are interpreting a geotechnical report table of contents.\n"
        "Return strict JSON only.\n"
        "Use the provided TOC source pages as the primary evidence.\n"
        "Use the deterministically parsed entries to correct OCR or parsing noise, but do not invent sections.\n"
        "Mark appendix/exhibit/attachment/boring-log/back-matter content as non_narrative.\n"
        "Choose the last top-level narrative section as the recommended narrative endpoint.\n"
        "Keep section titles and numbering source-faithful when possible."
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt + "\n\n" + build_llm_input(toc_pages, parsed_entries),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "toc_interpreter_result",
                "schema": openai_output_schema(),
                "strict": True,
            }
        },
    }
    req = request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace").strip()
        if error_body:
            raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {error_body}") from exc
        raise RuntimeError(f"OpenAI API returned HTTP {exc.code}: {exc.reason}") from exc

    output_text = response_payload.get("output_text")
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError("OpenAI response did not include output_text")

    llm_result = json.loads(output_text)
    toc_entries = llm_result.get("toc_entries")
    top_level_sections = llm_result.get("top_level_sections")
    recommendation = llm_result.get("narrative_end_recommendation")
    strategy = str(llm_result.get("strategy", "openai"))

    if not isinstance(toc_entries, list) or not isinstance(top_level_sections, list):
        raise ValueError("OpenAI response missing TOC entry arrays")

    selected: dict[str, object] | None = None
    if isinstance(recommendation, dict):
        report_page = int(recommendation["report_page"])
        section_title = str(recommendation["section_title"])
        section_number = recommendation.get("section_number")
        for entry in toc_entries:
            if (
                int(entry["report_page"]) == report_page
                and str(entry["title"]) == section_title
                and entry.get("section_number") == section_number
            ):
                selected = entry
                break
        if selected is None:
            selected = {
                "report_page": report_page,
                "title": section_title,
                "section_number": section_number,
            }
        strategy = f"openai:{recommendation.get('reason', strategy)}"
    else:
        strategy = f"openai:{strategy}"

    return build_final_payload(
        pages=pages,
        toc_page_pdf=toc_page_pdf,
        toc_entries=toc_entries,
        top_level_sections=top_level_sections,
        selected=selected,
        strategy=strategy,
    )


def interpret_toc(
    text: str,
    *,
    mode: str = "auto",
    model: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    load_dotenv()
    pages = split_pages(text)
    toc_page_pdf, toc_pages, parsed_entries = find_toc_pages(pages)

    if toc_page_pdf is None:
        return build_final_payload(
            pages=pages,
            toc_page_pdf=None,
            toc_entries=[],
            top_level_sections=[],
            selected=None,
            strategy="deterministic:toc_not_found",
        )

    if mode not in {"auto", "deterministic", "openai"}:
        raise ValueError(f"Unsupported mode: {mode}")

    if mode != "deterministic" and os.environ.get("OPENAI_API_KEY"):
        try:
            return call_openai_toc_interpreter(
                text=text,
                pages=pages,
                toc_page_pdf=toc_page_pdf,
                toc_pages=toc_pages,
                parsed_entries=parsed_entries,
                model=model or os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
                timeout_seconds=timeout_seconds,
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            if mode == "openai":
                raise RuntimeError(f"OpenAI TOC interpretation failed: {exc}") from exc

    return interpret_toc_deterministic(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpret TOC and return a narrative endpoint recommendation.")
    parser.add_argument("input_text", type=Path, help="Path to extracted text with page markers.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output JSON path. Defaults to stdout.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "deterministic", "openai"],
        default="auto",
        help="Choose TOC interpretation mode. 'auto' uses OpenAI when OPENAI_API_KEY is present.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional OpenAI model override. Defaults to OPENAI_MODEL or gpt-4.1-mini.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for the OpenAI API request when LLM mode is used.",
    )
    args = parser.parse_args()

    text = args.input_text.read_text(encoding="utf-8")
    payload = interpret_toc(
        text,
        mode=args.mode,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
    )
    content = json.dumps(payload, indent=2) + "\n"

    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
