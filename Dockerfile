FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=5000 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all 

# Add 32-bit architecture, update, and install the complete 'wine' umbrella suite
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget xvfb wine wine64 wine32 python3 python3-pip ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Pre-initialize the Wine prefix silently using the virtual display
RUN xvfb-run -a wineboot --init

WORKDIR /app
COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Sleep briefly to ensure complete internal path stabilization before starting python
CMD xvfb-run --server-args="-screen 0 1024x768x16" sh -c "sleep 3 && python3 bridge.py"
