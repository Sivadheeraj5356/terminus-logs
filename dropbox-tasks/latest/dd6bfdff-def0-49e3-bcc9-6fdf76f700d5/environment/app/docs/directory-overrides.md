# Directory overrides

BOILOFF_INPUT_DIR defaults to /app/data and must be an absolute path without parent traversal.

BOILOFF_OUTPUT_DIR defaults to /app/output and must be absolute.

BOILOFF_STATE_DIR defaults to /app/state and must be absolute.

When overrides are set, all input paths are resolved under BOILOFF_INPUT_DIR and outputs land under the overridden output and state directories.

BOILOFF_EXPORT_FROM_STAGE_ONLY accepts true or false (case insensitive). When true, only the stage file under BOILOFF_STATE_DIR is read from disk besides environment variables.
