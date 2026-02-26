FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

COPY metaffi-installer /tmp/metaffi-installer
RUN chmod +x /tmp/metaffi-installer && \
    /tmp/metaffi-installer -s && \
    rm /tmp/metaffi-installer

# Verify: metaffi --help prints usage and exits 0 (tolerate 2 for old builds)
RUN metaffi --help; test $? -eq 0 -o $? -eq 2
