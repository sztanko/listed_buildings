FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common \
        gdal-bin \
        libgdal-dev \
        build-essential \
        curl \
        git \
        make \
        ca-certificates \
        gnupg && \
    # Install Node.js LTS
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs && \
    # Install Tippecanoe
    apt-get install -y libsqlite3-dev zlib1g-dev && \
    git clone https://github.com/felt/tippecanoe.git /tmp/tippecanoe && \
    cd /tmp/tippecanoe && \
    make -j$(nproc) && \
    make install && \
    cd / && \
    rm -rf /tmp/tippecanoe && \
    # Install pmtiles CLI
    npm install -g pmtiles && \
    # Clean up
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3.12
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*