FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=5000 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all 

# Install dependencies, including software-properties-common to manage repositories safely
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common wget ca-certificates && \
    dpkg --add-architecture i386 && \
    apt-get update

# Install the correct universal Wine integration binaries along with a virtual display frame
RUN apt-get install -y --no-install-recommends \
    xvfb \
    wine-stable \
    python3 \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Pre-initialize Wine configurations quietly via the virtual display
RUN xvfb-run -a wineboot --init

WORKDIR /app
COPY . /app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Sleep briefly to ensure complete internal path stabilization before starting python
CMD xvfb-run --server-args="-screen 0 1024x768x16" sh -c "sleep 3 && python3 bridge.py"
