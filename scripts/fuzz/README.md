# Fuzzing SattLint-owned readers

Atheris-based coverage-guided fuzz targets for **SattLint's own** parsing and
validation code. These deliberately do **not** fuzz the `sattline-parser`
grammar — that package fuzzes its own parser in its own repository. Every
target here consumes raw bytes and exercises SattLint code that owns the input
format end-to-end.

## Targets

| Target | Entry points | Format |
|--------|--------------|--------|
| `icf_fuzzer.py` | `analyzers/icf/_icf_file_io.py` (`decode_icf_text`, `format_icf_text`, `parse_icf_file`) | `.icf` config files |
| `graphics_fuzzer.py` | `graphics/validation.py` (`validate_graphics_text`) | Serialized `.g`/`.y` graphics files |

Both readers are tolerant by design, so an exception escaping a target is a
genuine crash and is left uncaught for atheris to record.

## Running locally

atheris requires Linux and Python 3.11+ (a prebuilt wheel is provided):

```bash
python -m pip install -e ".[fuzz]"
python scripts/fuzz/icf_fuzzer.py -runs=100000 -max_len=4096
python scripts/fuzz/graphics_fuzzer.py -runs=100000 -max_len=4096
```

Useful libFuzzer-style flags: `-runs=N` (stop after N inputs), `-max_len=N`
(input size cap), `-timeout=S` (seconds per input), `-max_total_time=S` (stop
after S seconds). On a crash atheris prints the input, the reproducer, and
exits non-zero.

## CI

`.github/workflows/ci.yml` runs a bounded `fuzz-smoke` job (`-runs=200000`
per target, 10-minute timeout) on every PR. Treat this as a regression gate:
a crash in a SattLint-owned reader fails the job.
