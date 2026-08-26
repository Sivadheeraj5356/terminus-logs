# Patent document format

Each inbox file is a single JSON object describing one patent document:

- `doc_id`: a non-empty string that uniquely identifies the document.
- `tokens`: a non-empty array of non-empty strings, in reading order, one entry per token occurrence. Repeated tokens are expected and meaningful; do not deduplicate them.

Ingest rejects the whole run, without writing the corpus staging artifact, when any of the following holds:

- the inbox is empty or missing,
- a document has an empty `doc_id`,
- a document has an empty `tokens` array,
- any token string is empty,
- two documents share the same `doc_id`.

Duplicate `doc_id` values are an error even when the documents are otherwise identical. See `vocabulary.md` for how the accepted documents become the corpus staging snapshot.
