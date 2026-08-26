# Serial lineage

issuance.json records serial, issued_at, ca_id, and filename for each certificate file.

When multiple files share a serial, the row with the greatest issued_at timestamp wins. Losers receive duplicate_serial rejections.
