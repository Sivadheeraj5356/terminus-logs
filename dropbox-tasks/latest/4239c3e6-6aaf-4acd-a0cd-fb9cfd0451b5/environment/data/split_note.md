# Train / held-out split

Rows whose y is present are training data; rows whose y is blank are the held-out
deployment contacts to score. row_id is a stable key preserved across any
re-derivation of the data. The training rows are a case-control sample (subscribers
kept, non-subscribers down-sampled to about a one-to-one mix); the held-out contacts
arrive at the true, much lower deployment subscription rate. Every substantial
education group appears in both parts.
