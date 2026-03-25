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
APPENDIX_TITLE_PATTERNS = [
    re.compile(r"\bappendix\b", re.IGNORECASE),
    re.compile(r"\bappendices\b", re.IGNORECASE),
    re.compile(r"\breferences?\b", re.IGNORECASE),
]
EXHIBIT_TITLE_PATTERNS = [
    re.compile(r"\bexhibits?\b", re.IGNORECASE),
    re.compile(r"\battachments?\b", re.IGNORECASE),
    re.compile(r"\bplates?\b", re.IGNORECASE),
]
FIGURE_TABLE_TITLE_PATTERNS = [
    re.compile(r"\bfigures?\b", re.IGNORECASE),
    re.compile(r"\btables?\b", re.IGNORECASE),
    re.compile(r"\btable of figures\b", re.IGNORECASE),
]
BORING_LOG_TITLE_PATTERNS = [
    re.compile(r"\bboring logs?\b", re.IGNORECASE),
    re.compile(r"\bboring log attachments?\b", re.IGNORECASE),
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
    seen: set[tuple[str | None, str, int]] = set()

    for match in TOC_ENTRY_PATTERN.finditer(normalized):
        section_number = match.group(1) or None
        title = re.sub(r"\s+", " ", match.group(2)).strip(" .")
        report_page = int(match.group(3))
        key = (section_number, title.lower(), report_page)
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


def find_toc_pages(
    pages: list[tuple[int, str]],
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


def section_level(section_number: str | None, title: str) -> int:
    if isinstance(section_number, str) and section_number:
        return section_number.count(".") + 1
    if re.match(r"^[A-Z][A-Za-z/&,\-()' ]+$", title.strip()):
        return 1
    return 1


def classify_section_type(title: str) -> str:
    if any(pattern.search(title) for pattern in BORING_LOG_TITLE_PATTERNS):
        return "boring_logs"
    if any(pattern.search(title) for pattern in FIGURE_TABLE_TITLE_PATTERNS):
        return "figure_table"
    if any(pattern.search(title) for pattern in EXHIBIT_TITLE_PATTERNS):
        return "exhibit"
    if any(pattern.search(title) for pattern in APPENDIX_TITLE_PATTERNS):
        return "appendix"
    if title.strip():
        return "narrative"
    return "unknown"


def is_narrative_section(section: dict[str, object]) -> bool:
    return str(section.get("section_type")) == "narrative"


def is_top_level_section(section: dict[str, object]) -> bool:
    return int(section.get("level", 1)) == 1


def normalize_toc_sections(toc_entries: list[dict[str, object]]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for entry in toc_entries:
        title = str(entry.get("title", "")).strip()
        section_number = entry.get("section_number")
        sections.append(
            {
                "section_number": section_number,
                "title": title,
                "report_page": int(entry["report_page"]),
                "level": section_level(section_number if isinstance(section_number, str) else None, title),
                "section_type": classify_section_type(title),
            }
        )
    return sections


def build_fallback_payload(
    *,
    fallback_reason: str | None,
    notes: list[str],
    toc_sections: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "toc_sections": toc_sections or [],
        "recommended_narrative_end_report_page": None,
        "recommended_narrative_end_section_title": None,
        "confidence": "low",
        "notes": notes,
        "n_a_fields": [
            "recommended_narrative_end_report_page",
            "recommended_narrative_end_section_title",
        ],
        "fallback_reason": fallback_reason,
    }
    return payload


def choose_narrative_end_section(
    toc_sections: list[dict[str, object]],
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    if not toc_sections:
        return None, []

    top_level_sections = [section for section in toc_sections if is_top_level_section(section)]
    if not top_level_sections:
        top_level_sections = toc_sections

    for section in reversed(top_level_sections):
        if is_narrative_section(section):
            return section, top_level_sections
    return None, top_level_sections


def deterministic_toc_payload(
    toc_entries: list[dict[str, object]],
    *,
    fallback_reason: str | None = None,
    extra_notes: list[str] | None = None,
) -> dict[str, object]:
    toc_sections = normalize_toc_sections(toc_entries)
    if not toc_sections:
        notes = ["No TOC sections were available for interpretation."]
        if extra_notes:
            notes.extend(extra_notes)
        return build_fallback_payload(
            fallback_reason=fallback_reason or "no_toc_entries",
            notes=notes,
        )

    selected_section, top_level_sections = choose_narrative_end_section(toc_sections)
    notes = [
        f"Interpreted {len(toc_sections)} TOC sections.",
        f"Found {len(top_level_sections)} top-level sections.",
    ]
    if extra_notes:
        notes.extend(extra_notes)

    if selected_section is None:
        notes.append("No top-level narrative section could be identified.")
        return build_fallback_payload(
            fallback_reason=fallback_reason or "all_top_level_sections_non_narrative",
            notes=notes,
            toc_sections=toc_sections,
        )

    notes.append("Selected the last top-level narrative section as the recommended narrative endpoint.")
    payload: dict[str, object] = {
        "toc_sections": toc_sections,
        "recommended_narrative_end_report_page": int(selected_section["report_page"]),
        "recommended_narrative_end_section_title": str(selected_section["title"]),
        "confidence": "high",
        "notes": notes,
        "n_a_fields": [],
        "fallback_reason": fallback_reason,
    }
    return payload


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


def build_llm_input(
    toc_pages: list[tuple[int, str]] | None,
    parsed_entries: list[dict[str, object]],
) -> str:
    parts: list[str] = []
    if toc_pages:
        toc_page_blocks = [
            f"--- PDF Page {page_number} ---\n{page_text}".strip() for page_number, page_text in toc_pages
        ]
        parts.append("TOC source pages:\n" + "\n\n".join(toc_page_blocks))
    parts.append("Deterministically parsed TOC entries:\n" + json.dumps(parsed_entries, indent=2))
    return "\n\n".join(parts)


def openai_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "toc_sections",
            "recommended_narrative_end_report_page",
            "recommended_narrative_end_section_title",
            "confidence",
            "notes",
            "n_a_fields",
            "fallback_reason",
        ],
        "properties": {
            "toc_sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "section_number",
                        "title",
                        "report_page",
                        "level",
                        "section_type",
                    ],
                    "properties": {
                        "section_number": {"type": ["string", "null"]},
                        "title": {"type": "string"},
                        "report_page": {"type": "integer", "minimum": 1},
                        "level": {"type": "integer", "minimum": 1},
                        "section_type": {
                            "type": "string",
                            "enum": [
                                "narrative",
                                "appendix",
                                "exhibit",
                                "figure_table",
                                "boring_logs",
                                "unknown",
                            ],
                        },
                    },
                },
            },
            "recommended_narrative_end_report_page": {"type": ["integer", "null"], "minimum": 1},
            "recommended_narrative_end_section_title": {"type": ["string", "null"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "notes": {"type": "array", "items": {"type": "string"}},
            "n_a_fields": {"type": "array", "items": {"type": "string"}},
            "fallback_reason": {"type": ["string", "null"]},
        },
    }


def call_openai_toc_interpreter(
    *,
    toc_entries: list[dict[str, object]],
    toc_pages: list[tuple[int, str]] | None,
    model: str,
    timeout_seconds: int,
) -> dict[str, object]:
    prompt = (
        "You are interpreting a geotechnical report table of contents.\n"
        "Return strict JSON only.\n"
        "Use the TOC source pages as the primary evidence when available.\n"
        "Use the deterministically parsed TOC entries to correct OCR or parsing noise, but do not invent sections.\n"
        "Classify sections into one of: narrative, appendix, exhibit, figure_table, boring_logs, unknown.\n"
        "Choose the last top-level narrative section as the recommended narrative endpoint.\n"
        "Set level to 1 for top-level sections and increment for numbered subsections.\n"
        "Use confidence high, medium, or low.\n"
        "If no recommendation can be made, set recommended fields to null and explain why in notes and fallback_reason."
    )
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt + "\n\n" + build_llm_input(toc_pages, toc_entries),
                    }
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "toc_interpreter_output",
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
    if not isinstance(llm_result.get("toc_sections"), list):
        raise ValueError("OpenAI response missing toc_sections")
    return llm_result


def interpret_toc_entries(
    *,
    toc_entries: list[dict[str, object]],
    toc_pages: list[tuple[int, str]] | None = None,
    use_llm: bool = False,
    strict_openai: bool = False,
    llm_model: str = DEFAULT_OPENAI_MODEL,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    load_dotenv()

    if use_llm and os.environ.get("OPENAI_API_KEY"):
        try:
            return call_openai_toc_interpreter(
                toc_entries=toc_entries,
                toc_pages=toc_pages,
                model=llm_model,
                timeout_seconds=timeout_seconds,
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            if strict_openai:
                raise RuntimeError(f"OpenAI TOC interpretation failed: {exc}") from exc
            return deterministic_toc_payload(
                toc_entries,
                fallback_reason=f"openai_fallback:{exc}",
                extra_notes=["OpenAI TOC interpretation failed; deterministic fallback was used."],
            )

    if use_llm and not os.environ.get("OPENAI_API_KEY"):
        if strict_openai:
            raise RuntimeError("OpenAI TOC interpretation failed: OPENAI_API_KEY was not set")
        return deterministic_toc_payload(
            toc_entries,
            fallback_reason="openai_api_key_missing",
            extra_notes=["OPENAI_API_KEY was not set; deterministic fallback was used."],
        )

    return deterministic_toc_payload(toc_entries)


def interpret_toc(
    text: str,
    *,
    mode: str = "auto",
    model: str | None = None,
    timeout_seconds: int = 60,
) -> dict[str, object]:
    pages = split_pages(text)
    _, toc_pages, toc_entries = find_toc_pages(pages)

    if mode not in {"auto", "deterministic", "openai"}:
        raise ValueError(f"Unsupported mode: {mode}")

    if not toc_entries:
        return build_fallback_payload(
            fallback_reason="toc_not_found",
            notes=["No table of contents was found in the provided text."],
        )

    return interpret_toc_entries(
        toc_entries=toc_entries,
        toc_pages=toc_pages,
        use_llm=(mode in {"auto", "openai"}),
        strict_openai=(mode == "openai"),
        llm_model=model or os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        timeout_seconds=timeout_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpret TOC and return structured JSON.")
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
