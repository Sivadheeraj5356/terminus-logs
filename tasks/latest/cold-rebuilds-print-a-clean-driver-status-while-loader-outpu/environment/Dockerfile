FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  bash=5.2.15-2+b13 \
  patch=2.7.6-7 \
  ca-certificates=20230311+deb12u1 \
  coreutils=9.1-1 \
  cpio=2.13+dfsg-7.1 \
  tmux=3.3a-3 \
  asciinema=2.2.0-1 \
  && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
  && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PATH=/opt/verifier/bin:${PATH}
ENV TMUX_TMPDIR=/app/.harbor-tmux

COPY bundles/ /app/environment/bundles/
COPY cases/ /app/environment/cases/
COPY data/ /app/environment/data/
COPY deps/ /app/environment/deps/
COPY docs/ /app/environment/docs/
COPY driver/ /app/environment/driver/
COPY emit/ /app/environment/emit/
COPY frame/ /app/environment/frame/
COPY lane/ /app/environment/lane/
COPY lib/ /app/environment/lib/
COPY schemas/ /app/environment/schemas/
COPY state/ /app/environment/state/
COPY tools/ /app/environment/tools/
COPY work/ /app/environment/work/
COPY README.md /app/environment/README.md

RUN chmod +x /app/environment/driver/exec_w0.sh \
  /app/environment/work/run_w5.sh \
  /app/environment/tools/trace_parity.sh \
  /app/environment/tools/run_index_bind.sh \
  /app/environment/tools/run_parity_avail.sh \
  /app/environment/lib/stamp_k.sh

RUN mkdir -p /app/output /app/.staging /app/.harbor-tmux
