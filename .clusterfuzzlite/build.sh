#!/bin/bash -eu

# Build and install the project (explicit Python 3.13)
/usr/local/bin/python3.13 -m pip install .

# Copy fuzzers into $OUT (standard oss-fuzz Python approach)
for fuzzer in $(find $SRC -name '*_fuzzer.py'); do
  cp "$fuzzer" "$OUT/"
done

# Make python3 resolve to Python 3.13 for any post-build checks
rm -f /usr/local/bin/python3
ln -s /usr/local/bin/python3.13 /usr/local/bin/python3
