# state digest

`state_digest` is lowercase hex SHA-256 over UTF-8 bytes built as follows:

1. Sort `results` by `query_id` ascending (on-disk order).
2. For each row in that order, append one line:
   `query_id\tdecision\treason\tquorum_weight\tsignatures_verified\tunique_custodians\n`
3. Append one line:
   `stats\tqueries_total\tallowed\tdenied\tsignature_failures\tquorum_failures\trevoked_hits\n`

Use decimal integer formatting without padding. No extra newline beyond the final stats line.
