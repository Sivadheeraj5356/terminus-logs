FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tmux=3.3a-3 asciinema=2.2.0-1 make=4.3-4.1 ca-certificates=20230311+deb12u1 openssl=3.0.20-1~deb12u2 python3=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 pytest-json-ctrf==0.3.5

COPY Makefile go.mod README.md scenario_index.toml /app/environment/
COPY cmd /app/environment/cmd
COPY p1_slice /app/environment/p1_slice
COPY p2_pick /app/environment/p2_pick
COPY p3_win /app/environment/p3_win
COPY p4_shift /app/environment/p4_shift
COPY p5_div /app/environment/p5_div
COPY p6_note /app/environment/p6_note
COPY p7_rank /app/environment/p7_rank
COPY p8_seal /app/environment/p8_seal
COPY p9_types /app/environment/p9_types
COPY p7_emit /app/environment/p7_emit
COPY p7_load /app/environment/p7_load
COPY p7_pipe /app/environment/p7_pipe
COPY p7_chain /app/environment/p7_chain
COPY data /app/environment/data
COPY policy /app/environment/policy
COPY docs /app/environment/docs
COPY cfg /app/environment/cfg
COPY support /app/environment/support
COPY cache /app/environment/cache

RUN make -C /app/environment all
RUN mkdir -p /app/output
