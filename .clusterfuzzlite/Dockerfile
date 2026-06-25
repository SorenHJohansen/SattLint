FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:bb4b09f7376cd0f2188344e8b293428b8d2ee54c81b596fa0ef1cd7f8b29d1a1

# Compile Python 3.13 from source (base image has Ubuntu 20.04 with Python 3.11, project requires >=3.13)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget build-essential libssl-dev zlib1g-dev libncurses5-dev \
    libncursesw5-dev libreadline-dev libsqlite3-dev libgdbm-dev \
    libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev tk-dev libffi-dev \
    && wget -q https://www.python.org/ftp/python/3.13.3/Python-3.13.3.tar.xz \
    && tar -xf Python-3.13.3.tar.xz \
    && cd Python-3.13.3 \
    && ./configure --enable-shared \
    && make -j"$(nproc)" \
    && make altinstall \
    && cd .. && rm -rf Python-3.13.3 Python-3.13.3.tar.xz \
    && ldconfig \
    && /usr/local/bin/python3.13 -m ensurepip --upgrade \
    && /usr/local/bin/python3.13 -m pip install --upgrade pip setuptools atheris pyinstaller \
    && rm -rf /var/lib/apt/lists/*

COPY . $SRC/sattlint
WORKDIR $SRC/sattlint
COPY ./.clusterfuzzlite/build.sh $SRC/
