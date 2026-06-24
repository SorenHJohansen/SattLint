FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:bb4b09f7376cd0f2188344e8b293428b8d2ee54c81b596fa0ef1cd7f8b29d1a1

# Install Python 3.13 (base image has 3.11, project requires >=3.13)
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3.13 python3.13-dev python3.13-distutils python3.13-venv \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1000 \
    && python3 -m ensurepip --upgrade \
    && python3 -m pip install --upgrade pip setuptools wheel pyinstaller atheris

COPY . $SRC/sattlint
WORKDIR $SRC/sattlint
COPY ./.clusterfuzzlite/build.sh $SRC/
