FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y \
    build-essential zlib1g-dev libffi-dev libssl-dev \
    libbz2-dev libreadline-dev libsqlite3-dev liblzma-dev \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and build CPython 3.13 with --disable-gil
ARG PYTHON_VERSION=3.13.13
RUN wget -q https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
    && tar xzf Python-${PYTHON_VERSION}.tgz \
    && cd Python-${PYTHON_VERSION} \
    && ./configure --prefix=/opt/python-freethreaded --disable-gil --enable-optimizations --with-lto \
    && make -j$(nproc) \
    && make install \
    && cd / && rm -rf Python-${PYTHON_VERSION}*

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y libffi8 libssl3 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/python-freethreaded /opt/python-freethreaded
ENV PATH="/opt/python-freethreaded/bin:$PATH"
ENV PYTHON_GIL=0

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY main.py .

EXPOSE 8080
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
