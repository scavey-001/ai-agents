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
