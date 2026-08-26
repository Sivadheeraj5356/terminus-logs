FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c AS builder

WORKDIR /src
COPY firmware/skittle_rev_b.c /src/skittle_rev_b.c
COPY firmware/rack.h /src/rack.h
RUN gcc -O2 -o /src/skittle /src/skittle_rev_b.c && strip -s /src/skittle

FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

RUN mkdir -p /app/cabinet

COPY --from=builder /src/skittle /app/cabinet/skittle
RUN chmod 555 /app/cabinet/skittle

COPY data/cabinet/link_protocol.txt /app/cabinet/link_protocol.txt
COPY data/cabinet/service_menu.txt /app/cabinet/service_menu.txt
COPY data/cabinet/rom_strings.txt /app/cabinet/rom_strings.txt
COPY data/cabinet/pinout.txt /app/cabinet/pinout.txt
COPY data/cabinet/board_revisions.txt /app/cabinet/board_revisions.txt
COPY data/attract /app/attract
COPY data/flyer /app/flyer
COPY data/ladder /app/ladder
COPY data/tools /app/tools
COPY README.md /app/README.md

WORKDIR /app
