# alertagg 2.0.0 migration notes

The Reset() helper earlier releases exported for test harnesses is gone; aggregation state now clears itself between reporting windows and nothing under /app/project ever imported Reset() directly.
