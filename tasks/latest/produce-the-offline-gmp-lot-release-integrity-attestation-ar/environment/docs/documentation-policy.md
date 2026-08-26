# Documentation policy

Required batch release documentation types are listed in batch_policy.json under required_doc_types. A type counts only when documentation_manifest.json contains a row with matching doc_type and status approved. Rows with status signed, draft, or pending do not satisfy the requirement.

When a required type is missing or not approved, the documentation gate adds blocker missing-doc: followed by the doc type.

The documentation gate passes only when its blockers list is empty. Blockers are sorted lexicographically.
