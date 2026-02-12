# Testdata Catalog

This folder contains reference datasets for MCP QGIS test scenarios.

## Scenario folders

- `scenario-01-split-road`: split parcel into lots with internal road.
- `scenario-02-boundary-shift`: move shared boundary by fixed distance.
- `scenario-03-utilities-constraints`: utility corridors with exclusion zones.
- `scenario-04-crs-mismatch`: CRS mismatch detection and correction.
- `scenario-05-recovery-rollback`: mid-plan failure and rollback verification.

## Folder contract

Each scenario folder should include:

- `input/` source layers
- `expected/` expected outputs
- `meta.json` scenario metadata
- `notes.md` assumptions and known caveats
