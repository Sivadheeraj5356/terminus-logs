# Constraint policy

Permission rows carry an `order` field. When evaluating whether a principal-level pair may traverse the group or role channels, consider only rows whose source and destination levels match the pair.

The prevailing decision for a pair is taken from the matching row whose `order` value is smallest. If no row matches, the pair is denied.

This policy applies to group and role channel edges only.
