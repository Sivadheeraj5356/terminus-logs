# Zone apply operations

Primary-zone host promotion for partial-deploy rollback. apply-rollback.sh is the only apply entrypoint. It must verify inspect-manifest, plan-seal, egress-lane midpipe, wave-midpipe snapshot, and rollback-witness-bundle, then write the marker file /app/state/rollback-complete.ok with body ok.

Operators set ROLLBACK_INCIDENT_ID and ROLLBACK_ZONE in the environment. Wrong incident ids or missing zone tokens must exit non-zero. The legacy file /app/deploy/rollback-order.json is not an apply authority.
