FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv tmux asciinema ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app
COPY task_file/input_data/ /app/input_data/
COPY task_file/spec/ /app/spec/
RUN python3 -c "from pathlib import Path; p=Path('/app/input_data/public_frames.hex'); Path('/app/input_data/public_frames.bin').write_bytes(bytes.fromhex(p.read_text()))"
RUN mkdir -p /app/src && printf '%s\n' 'int main(void){return 0;}' > /app/src/beacon_replay.c
