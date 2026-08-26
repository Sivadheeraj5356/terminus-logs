# Append

`climconvert append --base PATH --append PATH --out PATH` concatenates two datasets along time.

## Compatibility

- Calendars must match exactly.
- Units origins may differ when calendars match; values are interpreted as calendar-qualified instants and written in the base units.
- Incompatible inputs fail with non-zero exit and leave no partial `--out` file.

## Ordering

Merged observations appear in ascending canonical chronological order. Variable rows stay aligned with their time coordinates.
