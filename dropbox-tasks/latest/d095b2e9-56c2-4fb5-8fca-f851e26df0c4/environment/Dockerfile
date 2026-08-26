FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV PATH="/opt/minizinc/bin:${PATH}"
RUN apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends ca-certificates tmux asciinema libstdc++6 zlib1g && rm -rf /var/lib/apt/lists/*
COPY vendor/minizinc.tgz.part-* /tmp/minizinc-parts/
RUN cat /tmp/minizinc-parts/minizinc.tgz.part-* > /tmp/minizinc.tgz && rm -rf /tmp/minizinc-parts && echo "b408e2a43645613225190e12fe14a3443064a9abf0164afbc84441d74be4525f  /tmp/minizinc.tgz" | sha256sum -c - && mkdir -p /opt/minizinc && tar -xzf /tmp/minizinc.tgz -C /opt/minizinc --strip-components=1 && ln -s /opt/minizinc/bin/minizinc /usr/local/bin/minizinc && rm /tmp/minizinc.tgz
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --retries 8 --timeout 60 --require-hashes -r /tmp/requirements.lock && rm /tmp/requirements.lock
RUN mkdir -p /app
WORKDIR /app
COPY --chmod=755 run_model.sh /app/run_model.sh
COPY data_schema.mzn instance.dzn instance.json contract.md output_contract.md README.md /app/
