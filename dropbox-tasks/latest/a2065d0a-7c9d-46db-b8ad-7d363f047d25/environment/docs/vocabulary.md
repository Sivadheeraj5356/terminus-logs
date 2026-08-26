# Corpus staging and vocabulary

`ldactl ingest` produces `/app/state/lda-corpus-staging.json` with schema string `lda-corpus/v1` and two members:

- `vocab`: the sorted list of distinct token strings across all accepted documents. Ordering is lexicographic by Unicode code point (byte order for ASCII). Each token's identifier is its zero-based index in this list.
- `docs`: one entry per document, sorted ascending by `doc_id`. Each entry has `doc_id` and `token_ids`, where `token_ids` is the document's tokens mapped through the vocabulary index, preserving the original token order and multiplicity.

The vocabulary order is independent of the order in which files are read; it depends only on the token strings themselves. The document order in the snapshot is independent of file names; it depends only on `doc_id`. These two orderings make the corpus staging snapshot a canonical, reproducible representation of the inbox.
