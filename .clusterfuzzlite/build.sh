#!/bin/bash -eu

# Build and install the project (explicit Python 3.13)
/usr/local/bin/python3.13 -m pip install .

# Build fuzzers into $OUT from repo-owned source harnesses only.
for fuzzer in $(find "$SRC/sattlint/src" -name '*_fuzzer.py'); do
  fuzzer_basename=$(basename -s .py "$fuzzer")
  fuzzer_package=${fuzzer_basename}.pkg

  pyinstaller --distpath "$OUT" --onefile --name "$fuzzer_package" "$fuzzer"

  echo "#!/bin/sh
# LLVMFuzzerTestOneInput for fuzzer detection.
this_dir=\$(dirname \"\$0\")
LD_PRELOAD=\$this_dir/sanitizer_with_fuzzer.so \
ASAN_OPTIONS=\$ASAN_OPTIONS:symbolize=1:external_symbolizer_path=\$this_dir/llvm-symbolizer:detect_leaks=0 \
\$this_dir/$fuzzer_package \$@" > "$OUT/$fuzzer_basename"
  chmod +x "$OUT/$fuzzer_basename"
done

# Make python3 resolve to Python 3.13 for any post-build checks
rm -f /usr/local/bin/python3
ln -s /usr/local/bin/python3.13 /usr/local/bin/python3
