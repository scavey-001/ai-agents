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
- Use `shared/scripts/detect_narrative_end.py` as a TOC-first narrative planner with heuristic fallback.
- Prefer TOC-guided planning to decide how many narrative pages to extract.
- For born-digital reports, direct text extraction should be the default path.

## Environment and Dependency Baseline

To reduce cross-machine drift between Codex and local development, this repository pins and documents runtime expectations.

### Python Version

- Target Python version is `3.12.12` (see `.python-version`).
- If you use `pyenv`, run `pyenv install 3.12.12` and `pyenv local 3.12.12`.

### Python Modules

- Install repo dependencies from source-controlled `requirements.txt`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

- Note: current runtime scripts use Python standard library modules only; keep `requirements.txt` updated whenever third-party packages are introduced.
- LLM-backed TOC interpretation requires the `openai` Python package from `requirements.txt`.

### Non-Python System Dependency

The extraction workflow depends on `pdftotext` being available on `PATH`.

- Ubuntu/Debian:

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils
```

- macOS (Homebrew):

```bash
brew install poppler
```

- Verify installation:

```bash
pdftotext -v
```

### LLM-backed TOC Interpreter (Optional)

`shared/scripts/detect_narrative_end.py` supports an optional LLM-backed TOC interpretation stage.

- Set `OPENAI_API_KEY` in your environment.
- Optional: set/override model via `--llm-model` (default: `gpt-4.1-mini`).

Example:

```bash
export OPENAI_API_KEY=your_key_here
python shared/scripts/detect_narrative_end.py \
  projects/demo_project_01/working/front_19_pages_text.txt \
  --use-llm-toc \
  --llm-model gpt-4.1-mini \
  --json-output projects/demo_project_01/working/front_19_pages_text_narrative_detection.json
```


## Agent Workflow Preferences

Repository-level agent operating preferences are documented in `AGENTS.md`.
