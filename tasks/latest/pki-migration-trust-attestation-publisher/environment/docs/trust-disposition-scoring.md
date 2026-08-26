# Trust disposition scoring

Deterministic trust_score values:

| disposition | reason | trust_score |
|-------------|--------|-------------|
| trusted | ok | 100 |
| needs_review | missing_proof | 50 |
| rejected | revoked | 0 |
| rejected | wrong_tree_size | 12 |
| rejected | duplicate_serial | 8 |
| rejected | stale_sth | 18 |
| rejected | untrusted_root | 22 |
| rejected | invalid_chain | 15 |
