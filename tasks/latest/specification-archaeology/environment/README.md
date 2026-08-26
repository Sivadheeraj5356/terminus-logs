# Runtime notes

The adjudicator is offline and standard-library only. The image installs the exact pytest tool versions into uv's persistent tool environment during the build, so `tests/test.sh` invokes a stable executable without a runtime cache or network dependency.
