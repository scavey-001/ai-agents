# Geotech Report Intake

## Goal

Create an organized project workspace and capture the essential context from an incoming geotechnical report package.

For the current phase, intake should emphasize whether the report is a preliminary geotechnical report and whether boring logs are present.

## Steps

1. Confirm project metadata and source document list.
2. Inventory incoming files under the project `input/` folder.
3. Convert PDFs to text when machine-readable extraction is possible.
4. Determine whether the package appears to include a preliminary geotechnical report.
5. Determine whether boring logs, appendices, or a boring summary table are present.
6. Record missing or unreadable items in the issue log.

## Outputs

- Project metadata JSON
- File inventory
- Intake note stating likely report type
- Intake note stating whether boring-log extraction is feasible from the provided material
- Intake notes in the project `working/` folder
