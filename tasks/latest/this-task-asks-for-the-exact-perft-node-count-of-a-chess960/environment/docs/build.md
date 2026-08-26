# Build and run

Build with the Makefile at the project root: running "make" from /app
produces the binary at /app/build/chess960_perft. The build uses only a
standard C++17 toolchain already installed in the image; it needs no
network access and no additional packages.

Run the binary directly with no arguments: ./build/chess960_perft. It
reads the position file and writes the output file described in
io_contract.md, using the default paths unless POSITION_PATH or
OUTPUT_PATH override them.
