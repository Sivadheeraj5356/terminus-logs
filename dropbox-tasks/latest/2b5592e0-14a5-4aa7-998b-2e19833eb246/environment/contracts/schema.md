# Input schema

The model reads `/app/data/service_ledger.csv`. One row is one repair ticket; the numeric
fields are stored as text, so read them in as numbers before modeling.

| column | type | notes |
|---|---|---|
| `ticket_id` | string | ticket identifier; may repeat across duplicate rows |
| `service_month` | integer | service month, oldest to newest; the newest is the open batch to score, a few months past the last labeled month |
| `equipment_class` | string | equipment class the ticket covers |
| `job_complexity` | numeric | job-complexity score of the ticket |
| `parts_replaced` | integer | number of parts replaced on the first visit |
| `tech_experience_years` | numeric | years of experience of the assigned technician |
| `prior_tickets_90d` | integer | prior tickets on the asset in the last 90 days; -1 encodes a value that was never captured |
| `dispatch_channel` | string | how the ticket was dispatched: `phone`, `portal` or `auto`; occasional junk tokens appear |
| `record_type` | string | `live` for real tickets, `qa_audit` for internal audit tickets that must be dropped from the cohort |
| `qa_signoff_code` | numeric | quality sign-off score in `[0, 1]`; on settled tickets it reflects the resolved outcome, on open tickets it still carries a provisional value |
| `repeat_visit` | integer or blank | 1 if the ticket needed a repeat truck-roll within thirty days, 0 if resolved first time; blank on the open tickets |

A field that only settles once the repeat outcome is known was set after the fact and is
not a legitimate input to a live open-ticket decision.
