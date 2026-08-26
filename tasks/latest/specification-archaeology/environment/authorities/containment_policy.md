# Containment policy CP-9

A safe cut disables trust objects so no rejected or compromised path reaches a service, while at least one accepted path remains for each critical service whenever any safe alternative exists. Mandatory emergency services with a valid exception must remain reachable. Candidate trust objects are those marked `disableable` in evidence. Optimize in order: fewest disabled objects; lowest total disruption weight of services losing all accepted paths; lexicographically smallest sorted object-ID list.

Classify policy statements as `PRECEDENCE_RESOLVED`, `SCOPE_DISTINGUISHED`, `SUPERSEDED`, or `UNRESOLVED`. Report only unresolved conflict IDs in the plan; their affected paths fail closed.

