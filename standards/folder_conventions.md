# Folder Conventions

## Purpose

Keep repository structure predictable so agents and humans can locate inputs, intermediate work, and outputs quickly.

## Rules

- `standards/` stores repository-wide operating conventions.
- `shared/` stores reusable assets across multiple agents.
- `agents/<agent_name>/` stores assets specific to one agent.
- `projects/<project_name>/input/` stores source materials exactly as received.
- `projects/<project_name>/working/` stores extracted text, notes, inventories, and intermediate analysis.
- `projects/<project_name>/output/` stores client-ready or workflow-ready final deliverables.

## Naming

- Use lowercase directory names with underscores only when needed for readability.
- Keep project names stable once created.
- Avoid spaces in file and folder names.
