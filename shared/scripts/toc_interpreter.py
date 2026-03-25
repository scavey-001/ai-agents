#!/usr/bin/env python3
"""LLM-backed TOC interpreter with deterministic fallback."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


SECTION_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("appendix", re.compile(r"\bappendix|appendices\b", re.IGNORECASE)),
    ("exhibit", re.compile(r"\bexhibit|exhibits|attachment|attachments\b", re.IGNORECASE)),
    ("figure_table", re.compile(r"\bfigure|figures|table|tables|plate|plates\b", re.IGNORECASE)),
    ("boring_logs", re.compile(r"\bboring log|boring logs\b", re.IGNORECASE)),
]

TOC_INTERPRETER_SCHEMA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "toc_interpreter_output.json").read_text(encoding="utf-8")
)


def classify_section_type(title: str) -> str:
    for section_type, pattern in SECTION_TYPE_PATTERNS:
        if pattern.search(title):
            return section_type
    return "narrative"


def estimate_level(section_number: str | None) -> int:
    if not section_number:
        return 1
    return section_number.count(".") + 1


def deterministic_interpretation(toc_entries: list[dict[str, object]]) -> dict[str, Any]:
    toc_sections: list[dict[str, Any]] = []
    selected_entry: dict[str, object] | None = None

    for entry in toc_entries:
        section_number = entry.get("section_number")
        title = str(entry.get("title", "")).strip()
        report_page = int(entry.get("report_page", 0) or 0)
        if not title or report_page < 1:
            continue

        section_type = classify_section_type(title)
        level = estimate_level(section_number if isinstance(section_number, str) else None)
        toc_sections.append(
            {
                "section_number": section_number if isinstance(section_number, str) else None,
                "title": title,
                "report_page": report_page,
                "level": level,
                "section_type": section_type if section_type in {"appendix", "exhibit", "figure_table", "boring_logs"} else "narrative",
            }
        )

    for section in reversed(toc_sections):
        if section["level"] == 1 and section["section_type"] == "narrative":
            selected_entry = section
            break

    if selected_entry is None:
        for section in reversed(toc_sections):
            if section["section_type"] == "narrative":
                selected_entry = section
                break

    return {
        "toc_sections": toc_sections,
        "recommended_narrative_end_report_page": selected_entry["report_page"] if selected_entry else None,
        "recommended_narrative_end_section_title": selected_entry["title"] if selected_entry else None,
        "confidence": "low",
        "notes": ["Deterministic fallback used; no LLM interpretation applied."],
        "n_a_fields": [] if selected_entry else ["recommended_narrative_end_report_page", "recommended_narrative_end_section_title"],
        "fallback_reason": "llm_unavailable_or_disabled",
    }


def llm_interpretation(
    toc_entries: list[dict[str, object]],
    model: str,
    api_key: str,
) -> dict[str, Any]:
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: openai. Install it from requirements.txt.") from exc

    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a strict TOC interpreter. Return JSON only and match the provided schema exactly. "
        "Use section_type values: narrative, appendix, exhibit, figure_table, boring_logs, unknown. "
        "When unknown or low-confidence, use n_a_fields."
    )
    user_payload = {"toc_entries": toc_entries}
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "text", "text": json.dumps(user_payload)}]},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "toc_interpreter_output",
                "schema": TOC_INTERPRETER_SCHEMA,
                "strict": True,
            }
        },
    )
    return json.loads(response.output_text)


def interpret_toc_entries(
    toc_entries: list[dict[str, object]],
    use_llm: bool = False,
    llm_model: str = "gpt-4.1-mini",
    api_key: str | None = None,
) -> dict[str, Any]:
    if not toc_entries:
        return {
            "toc_sections": [],
            "recommended_narrative_end_report_page": None,
            "recommended_narrative_end_section_title": None,
            "confidence": "low",
            "notes": ["No TOC entries available."],
            "n_a_fields": ["recommended_narrative_end_report_page", "recommended_narrative_end_section_title"],
            "fallback_reason": "no_toc_entries",
        }

    if not use_llm:
        return deterministic_interpretation(toc_entries)

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        fallback = deterministic_interpretation(toc_entries)
        fallback["notes"].append("OPENAI_API_KEY missing; used deterministic fallback.")
        fallback["n_a_fields"] = sorted(set([*fallback["n_a_fields"], "llm_response"]))
        fallback["fallback_reason"] = "missing_openai_api_key"
        return fallback

    try:
        return llm_interpretation(toc_entries=toc_entries, model=llm_model, api_key=key)
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        fallback = deterministic_interpretation(toc_entries)
        fallback["notes"].append(f"LLM interpretation failed: {exc}")
        fallback["n_a_fields"] = sorted(set([*fallback["n_a_fields"], "llm_response"]))
        fallback["fallback_reason"] = "llm_error_fallback"
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpret TOC entries with optional LLM backing.")
    parser.add_argument("toc_json", type=Path, help="Path to a JSON file containing TOC entries.")
    parser.add_argument("-o", "--output", type=Path, help="Optional output JSON path. Defaults to stdout.")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM-backed TOC interpretation.")
    parser.add_argument("--llm-model", default="gpt-4.1-mini", help="Model name for LLM TOC interpretation.")
    parser.add_argument("--api-key", help="Optional API key override. Defaults to OPENAI_API_KEY env var.")
    args = parser.parse_args()

    payload = json.loads(args.toc_json.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "toc_entries" in payload:
        toc_entries = payload["toc_entries"]
    else:
        toc_entries = payload
    if not isinstance(toc_entries, list):
        raise SystemExit("Expected TOC entries as a list or {'toc_entries': [...]} payload.")

    interpreted = interpret_toc_entries(
        toc_entries=toc_entries,
        use_llm=args.use_llm,
        llm_model=args.llm_model,
        api_key=args.api_key,
    )
    content = json.dumps(interpreted, indent=2) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
