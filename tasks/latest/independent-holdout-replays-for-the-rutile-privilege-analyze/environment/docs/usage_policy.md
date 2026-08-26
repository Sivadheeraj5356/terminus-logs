# Usage weight policy

Edge weights default to one when no usage telemetry row names the same directed pair.

When telemetry exists for a pair, weight equals the recorded hit count unless that count exceeds nine, in which case weight is nine.
