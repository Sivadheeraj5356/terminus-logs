# v5
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.3.2 \
    pytest-json-ctrf==0.5.2

COPY task_data/codex.txt        /opt/task_data/codex.txt
COPY task_data/sessions.json    /opt/task_data/sessions.json
COPY task_data/tribunal-game    /opt/task_data/tribunal-game
RUN chmod +x /opt/task_data/tribunal-game
COPY task_data/entrypoint.sh    /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && \
    ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

ENV PATH="/usr/local/go/bin:${PATH}"

RUN mkdir -p /workspace
WORKDIR /workspace

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["bash"]
