# Preliminary Geotech Boring Basics

## Goal

For a preliminary geotechnical report, answer three baseline questions from the boring logs or boring summary:

1. How many borings were performed?
2. How deep did they go?
3. Did any of them hit refusal?

## Inputs

- Preliminary geotechnical report narrative
- Boring logs
- Appendices
- Boring location or exploration summary tables

## Extraction Workflow

1. Confirm the report appears to be preliminary geotechnical work.
2. Locate every boring ID referenced in the report and appendices.
3. Count distinct borings, ignoring duplicate references to the same boring.
4. Record each boring termination depth exactly as shown, including units.
5. Record whether refusal is explicitly stated for each boring.
6. If the report is ambiguous, preserve the ambiguity instead of forcing a conclusion.

## Required Output

- Total boring count
- A per-boring list with boring ID and termination depth
- A project-level answer on whether refusal was observed
- Open questions for any missing or unreadable log data

## Guardrails

- Do not estimate termination depth from page layout or graphic scaling.
- Do not infer refusal from abbreviations unless the report legend or notes support that reading.
- If logs are missing, state that the questions cannot be fully answered from the available package.
