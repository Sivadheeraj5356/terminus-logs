# Vendored build dependencies

The `apt/amd64` directory contains the complete Debian package closure needed by the pinned Bookworm AMD64 calibration image for GCC, libc development headers, tmux, and asciinema. Package filenames include their exact Debian versions, and the Dockerfile rejects any unexpected target architecture.

The `wheels` directory contains the five pure-Python wheels named and SHA-256 locked in `requirements.lock`. The Dockerfile installs them with `PIP_NO_INDEX=1`, `--no-index`, `--require-hashes`, and `--no-deps`.

The final image build performs no apt update, package download, index lookup, or Python package download. A network-disabled build is the acceptance check for this vendor directory.
