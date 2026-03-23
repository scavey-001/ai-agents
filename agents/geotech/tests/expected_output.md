# Expected Output

The geotech agent should produce:

- A concise project summary in Markdown
- A structured JSON summary conforming to `agents/geotech/schemas/geotech_summary.json`
- A boring-log summary that answers count, depth, and refusal questions
- Clear risk flags with confidence ratings when the workflow expands beyond boring basics
- Explicit open questions when source material is incomplete
- A TOC-aware intake check that can justify whether enough front-matter pages were OCR'd to cover the full narrative section

For the current demo sample:

- The TOC indicates the narrative continues through `9 Limitations` on report page `16`
- Any initial narrative OCR plan should therefore cover at least through report page `16`, not stop at the first mention of `boring logs` or `attachments`
- See `agents/geotech/tests/fixtures/demo_project_01_toc_sections.md`
