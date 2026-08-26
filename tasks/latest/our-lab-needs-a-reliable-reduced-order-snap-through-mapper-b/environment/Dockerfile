FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        python3 \
        python3-pip \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

RUN useradd --create-home --uid 10001 --shell /bin/bash analyst \
    && install -d -o analyst -g analyst /app/bin /app/results /app/workbench \
    && install -d -o root -g root -m 0755 /app/cases /app/docs

COPY docs/ /app/docs/
COPY cases/ /app/cases/
COPY --chown=analyst:analyst workbench/ /app/workbench/
COPY --chmod=0755 verifier-tools/seal-kirigami-tests /usr/local/sbin/seal-kirigami-tests
COPY --chmod=0755 verifier-tools/run-kirigami-verifier /usr/local/sbin/run-kirigami-verifier
COPY --chmod=0755 verifier-tools/container-entrypoint /usr/local/bin/container-entrypoint
COPY --chmod=0755 verifier-tools/agent-shell /usr/local/bin/agent-shell

RUN usermod --shell /usr/local/bin/agent-shell root

RUN find /app/docs /app/cases -type d -exec chmod 0555 {} + \
    && find /app/docs /app/cases -type f -exec chmod 0444 {} +

WORKDIR /app
ENV HOME=/root
ENV SHELL=/usr/local/bin/agent-shell
ENTRYPOINT ["/usr/local/bin/container-entrypoint"]
CMD ["sleep", "infinity"]
