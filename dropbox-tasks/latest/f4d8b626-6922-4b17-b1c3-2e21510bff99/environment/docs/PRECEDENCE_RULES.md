# Precedence rules

1. Drop any report whose report_id appears as another report supersedes value.
2. Group remaining reports by dive_lane.
3. Within each lane keep exactly one report: lowest confidence_rank wins; on equal confidence_rank keep highest revision; tie-break report_id ascending.
4. Output resolved list sorted by report_id ascending.
