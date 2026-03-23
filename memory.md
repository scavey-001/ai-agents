# Memory

## Latest Session Result

- Direct PDF text extraction is now the primary extraction path
- PaddleOCR fallback path has been removed from the repo
- Demo outputs created for TOC-first planning:
- `projects/demo_project_01/working/front_19_pages_text.txt`
- `projects/demo_project_01/working/front_19_pages_text_narrative_only.txt`
- `projects/demo_project_01/working/front_19_pages_text_narrative_detection.json`
- TOC-guided narrative planner now selects the last top-level narrative TOC section instead of relying on a hard-coded section name
- For the demo sample, the selected end section is `Limitations` on report page `16`, mapped to extracted PDF page `19`
- Working folder has been cleaned so only the current `front_19_pages_text*` artifacts remain
- Geotech parser has been rerun against `front_19_pages_text_narrative_only.txt`
- Current structured output is `projects/demo_project_01/output/geotech_summary.json`
- New architectural direction chosen: use an LLM as a bounded TOC interpreter instead of relying only on hard-coded TOC parsing
- Preferred future pattern:
- script extracts first `3-5` pages or TOC pages
- LLM returns structured JSON for TOC sections, narrative endpoint, and section types
- local scripts use that JSON to drive the next extraction step
- Key extracted narrative facts already visible:
- 42 soil borings
- array borings to approximately 20 feet BGS or practical refusal
- substation borings reached practical refusal at approximately 28.5 feet and 25.9 feet BGS
- Parser now converts narrative boring facts into structured JSON at `projects/demo_project_01/output/geotech_summary.json`
- Demo TOC has been captured in `agents/geotech/tests/fixtures/demo_project_01_toc_sections.md`
- Important TOC result: narrative appears to continue through `9 Limitations` on report page `16`
- Next recommended step: design and implement an LLM-backed `toc_interpreter` stage that outputs strict JSON

## 1. Project Overview

- Repository: `ai-agents`
- Purpose: structured workspace for domain-specific AI agents, shared utilities, and project-level inputs/outputs
- Current domain focus: geotechnical SME agent
- Current report focus: preliminary geotechnical reports
- Current extraction focus: basic boring-log facts from narrative/report text

## 2. Current Objectives

- Stabilize fast text extraction for large geotechnical PDFs
- Detect likely end of narrative/front matter before exhibits
- Use TOC-guided planning as the primary narrative-range strategy
- Understand report sections as risk-bearing sections relevant to utility-scale solar review
- Shift TOC understanding toward an LLM-assisted structured interpretation step
- Extract boring basics:
- total boring count
- general boring depths
- whether refusal is reported
- Convert extracted narrative into structured geotech JSON output

## 3. Active Tasks

- Design an LLM-backed `toc_interpreter` stage
- Define strict JSON output for TOC sections, section types, and recommended narrative endpoint
- Keep initial LLM input small, ideally first `3-5` pages or TOC pages only
- Use TOC sections to determine how many pages must be extracted for the main narrative
- Keep heuristic detection only as a fallback
- Extend parsing beyond narrative-level boring facts when full boring-log attachments are needed
- Decide whether to add a single wrapper intake command for project processing
- Keep `memory.md` updated at the end of each work session

## 4. Key Decisions Made

- Use direct PDF text extraction as the default workflow
- Remove image OCR fallback from the repo workflow
- Trim extraction scope before model analysis instead of feeding full 300+ page reports
- Focus geotech agent scope first on preliminary geotech reports and boring basics
- Ignore Windows `Zone.Identifier` sidecar files via `.gitignore`
- Use the table of contents as the preferred guide for determining the narrative OCR window when available
- Determine the narrative endpoint from the last top-level narrative TOC section, walking backward from the end and skipping appendix/exhibit-style sections
- Prefer a hybrid architecture: deterministic scripts for extraction/storage, LLMs for TOC interpretation and report-structure judgment

## 5. Assumptions

- Most useful report narrative is near the front of the report
- Exhibits/attachments/boring logs often begin after the main narrative
- Boring count/depth/refusal may be available in narrative before reviewing full boring logs
- Around 98% of target reports are expected to include some form of table of contents
- Most target reports are born-digital PDFs, not scanned image documents

## 6. Known Issues / Bugs

- TOC parsing still has a few imperfect entries in the JSON metadata
- Heuristic narrative detection can still cut off too early and should remain fallback-only
- Full boring-log extraction is not implemented yet
- Some tracked `__pycache__` artifacts already exist in git history and may need separate cleanup later
- Current TOC parsing is serviceable for the demo sample but likely too brittle long-term without LLM assistance

## 7. File Structure Notes

- Root docs:
- `README.md`
- `memory.md`
- Standards:
- `standards/`
- Shared scripts and schemas:
- `shared/scripts/`
- `shared/schemas/`
- Geotech agent:
- `agents/geotech/`
- Demo project:
- `projects/demo_project_01/input/`
- `projects/demo_project_01/working/`
- `projects/demo_project_01/output/`
- Local runtime/cache:
- `.venv/`
- `.runtime/`

## 8. How to Resume Work

- 1. Confirm repo root is `/home/scavey/src/ai-agents`
- 2. Read `memory.md` first for current state
- 3. Review latest working artifacts in `projects/demo_project_01/working/`
- 4. Confirm OCR outputs exist:
- `front_19_pages_text.txt`
- `front_19_pages_text_narrative_only.txt`
- `front_19_pages_text_narrative_detection.json`
- 5. Inspect `agents/geotech/scripts/parse_geotech_text.py`
- 6. Read `agents/geotech/tests/fixtures/demo_project_01_toc_sections.md`
- 7. Start with the new LLM-assisted TOC interpretation direction
- 8. Design a strict JSON schema for `toc_interpreter` output
- 9. Use that output to decide the target narrative page range, then rerun parsing as needed
- 10. Update `memory.md` at the end of the session with new decisions, tasks, and issues
