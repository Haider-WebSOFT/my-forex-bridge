FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=5000 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all 

RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget xvfb wine64 wine32 python3 python3-pip ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN xvfb-run -a wineboot --init

WORKDIR /app
COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Sleep for 3 seconds to let xvfb completely stabilize before executing python
CMD xvfb-run --server-args="-screen 0 1024x768x16" sh -c "sleep 3 && python3 bridge.py"
