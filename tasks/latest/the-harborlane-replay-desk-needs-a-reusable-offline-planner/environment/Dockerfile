FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS taskfiles

COPY task_file/ /task_file/

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm-256color
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
	        asciinema \
	        bash \
	        ca-certificates \
	        coreutils \
	        ghc \
	        less \
	        libgmp-dev \
	        nano \
	        procps \
	        python-is-python3 \
	        python3-venv \
	        tmux \
 && rm -rf /var/lib/apt/lists/* \
 && python -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/python -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

COPY --from=taskfiles /task_file/ /

WORKDIR /app

RUN chmod +x /opt/harborlane/scripts/model.py /opt/harborlane/scripts/baseline.py \
 && mkdir -p /logs/agent /logs/artifacts /logs/verifier /var/lib/harborlane/out /tmp/harborlane-ghc \
 && chmod 0777 /logs /logs/agent /logs/artifacts /logs/verifier \
 && tmux -V \
 && asciinema --version \
 && command -v bash \
 && command -v python3 \
 && python3 -m pip --version \
 && command -v ghc \
 && command -v runghc \
 && /opt/verifier-venv/bin/python -m pytest --version \
 && test -f /app/Main.hs \
 && python /opt/harborlane/scripts/model.py --json >/tmp/harborlane-model-smoke.json \
 && ghc -fno-code -odir /tmp/harborlane-ghc -hidir /tmp/harborlane-ghc /app/Main.hs

CMD ["bash"]
