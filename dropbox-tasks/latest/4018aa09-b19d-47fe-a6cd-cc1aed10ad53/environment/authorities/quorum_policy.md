# Witness quorum policy WQ-4

Severity HIGH requires two independent eligible authorities; CRITICAL requires three. A witness counts only when its authority was valid at signing, incident scope matches, and its commitment root equals the profile evidence root. Authorities sharing the same `independence_parent` contribute one vote in total. Duplicate or delegated identities never add votes. Use the lexicographically first witness from each eligible independence group for evidence citations.

