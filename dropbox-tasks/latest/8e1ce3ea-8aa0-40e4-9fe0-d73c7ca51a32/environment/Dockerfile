FROM gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

# Install system dependencies and Python for tests
# Note: make is required as agent needs to rebuild after fixes (debugging task carve-out)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        make=4.3-4.1 && \
    rm -rf /var/lib/apt/lists/*

# Install Python test dependencies with explicit versions
COPY requirements.txt /tmp/requirements.txt
RUN pip install --break-system-packages -r /tmp/requirements.txt

WORKDIR /app

# Copy build configuration generator
COPY generate_build_config.sh /app/

# Copy project structure
COPY include/ /app/include/
COPY src/ /app/src/
COPY config/ /app/config/
COPY docs/ /app/docs/
COPY Makefile /app/

# Build the buggy binary (debugging task - agent will rebuild after fixing)
RUN make clean && make all

# Create output directory
RUN mkdir -p /app/output
