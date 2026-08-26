# TF-IDF preview (commentary only)

The workspace ships a decoy module that computes a TF-IDF style term-weight preview over a corpus staging snapshot. It exists only as illustrative commentary about the corpus and is not part of any pipeline stage. It is never called by ingest, sample, export, or status, and it has no effect on any produced artifact.

Do not wire the TF-IDF preview into the topic-allocation pipeline. Topic term weights come exclusively from the smoothed posterior in `topic-ranking.md`; the TF-IDF preview is unrelated to that computation and must remain off the hot path.
