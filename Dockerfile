FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PORT=5000

# Install dependencies, Wine emulator, and Python
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    wget xvfb xauth dbus-x11 supervisor \
    wine64 wine32 ca-certificates python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Install python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Start a virtual display background layer and run our python gateway bridge
CMD xvfb-run -a python3 bridge.py