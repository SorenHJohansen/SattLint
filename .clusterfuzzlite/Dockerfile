FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:bb4b09f7376cd0f2188344e8b293428b8d2ee54c81b596fa0ef1cd7f8b29d1a1
COPY . $SRC/sattlint
WORKDIR $SRC/sattlint
COPY ./.clusterfuzzlite/build.sh $SRC/
