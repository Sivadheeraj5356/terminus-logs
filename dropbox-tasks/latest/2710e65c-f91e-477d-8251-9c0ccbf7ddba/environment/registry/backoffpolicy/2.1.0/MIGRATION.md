# backoffpolicy 2.1.0 migration notes

Backoff() now returns a duration instead of a fixed step count; nothing under /app/project reads either return value, so this only matters to callers outside this registry.
