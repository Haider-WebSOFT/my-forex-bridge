FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=5000 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all 

RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget xvfb wine wine64 wine32 python3 python3-pip ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# We run wineboot right as the container turns on, right before Python takes over
CMD xvfb-run --server-args="-screen 0 1024x768x16" sh -c "wineboot --init && sleep 3 && python3 bridge.py"
