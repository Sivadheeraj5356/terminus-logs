# CT inclusion proof contract

Each proof JSON under ct_logs/proofs/ contains serial, tree_size, leaf_index, and path (sibling hashes).

proof.tree_size must equal sth.tree_size from ct_logs/sth.json. Mismatches are wrong_tree_size rejections.

Proofs are keyed by serial and leaf_index when duplicate serials appear in one bundle.
