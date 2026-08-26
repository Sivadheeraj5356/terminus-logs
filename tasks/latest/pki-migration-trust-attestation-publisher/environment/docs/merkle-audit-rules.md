# Merkle audit rules

Leaf hashes are carried in b161aa7f_entries.jsonl. Inclusion verification walks path siblings using leaf_index parity at each tree level.

The computed root must equal sth.root_hash for tree_size matching the signed tree head.

VerifyPath uses index-based sibling walks, not lexicographic string comparison of hex digests.
