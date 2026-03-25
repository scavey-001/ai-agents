# AI Agents

This repository provides a structured workspace for domain-specific AI agents, shared standards, reusable schemas, and project-specific working areas.

## Repository Layout

- `standards/`: conventions for folders, outputs, and confidence ratings
- `shared/`: common schemas, templates, and utility scripts
- `agents/`: agent-specific instructions, skills, schemas, scripts, and tests
- `projects/`: per-project input, working, and output folders

## Current Agent

- `agents/geotech/`: geotechnical subject matter agent scaffold

## Getting Started

1. Place source files for a project in `projects/<project_name>/input/`.
2. Use `projects/<project_name>/working/` for intermediate artifacts.
3. Write final deliverables to `projects/<project_name>/output/`.
4. Reuse shared conventions from `standards/` and `shared/`.

## Text Extraction Workflow

- `shared/scripts/pdf_to_text.py` uses direct PDF text extraction via `pdftotext`.
- Write extracted text to `projects/<project_name>/working/`.
- Use `shared/scripts/toc_interpreter.py` to convert TOC content into structured JSON with a recommended narrative endpoint.
- Use `shared/scripts/detect_narrative_end.py` as a TOC-first narrative planner with heuristic fallback.
- Prefer TOC-guided planning to decide how many narrative pages to extract.
- For born-digital reports, direct text extraction should be the default path.

## OpenAI Configuration

- Put `OPENAI_API_KEY=...` in a local `.env` file at the repo root for LLM-backed TOC interpretation.
- `.env` is gitignored; use `.env.example` as the safe template.
- `shared/scripts/toc_interpreter.py` runs in `auto` mode by default, using OpenAI when `OPENAI_API_KEY` is present and falling back to deterministic TOC logic otherwise.
