# Boring Log Extraction

## Goal

Extract the most basic boring-log facts from a preliminary geotechnical report or its appendices.

## Focus Areas

- Total number of borings
- Boring IDs such as `B-1`, `B-2`, or similar
- Termination depth for each boring
- Whether refusal is explicitly noted for any boring
- Ambiguities where the boring count or end depth cannot be confirmed

## Output Expectations

- Maintain original units
- Keep each boring traceable to its source page or section
- Mark uncertain readings with a confidence rating

## Questions This Skill Must Answer

1. How many borings are shown or referenced?
2. How deep did each boring go?
3. Did any boring hit refusal?

## Refusal Guardrails

- Do not assume refusal just because a boring stopped at a shallow depth.
- Do not equate auger refusal, rock refusal, and practical termination unless the report does.
- If the document uses related language such as `refusal`, `auger refusal`, `hard refusal`, or `refusal on rock`, cite the exact phrasing in the output.
- If refusal cannot be confirmed from source text, state that it is not confirmed.
