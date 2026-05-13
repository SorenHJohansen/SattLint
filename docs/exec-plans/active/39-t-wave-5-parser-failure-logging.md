# T-Wave-5 Parser Failure Logging

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-026. After this work lands, parser failure paths will emit structured log records with file, stage, and context information instead of only raising exceptions, while strict parser behavior remains unchanged. The observable proof is that focused parser tests can capture log output for decode, parse, or transform failures, and `sattlint syntax-check` continues to behave strictly with no silent fallback behavior.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `src/sattline_parser/api.py`, `src/sattline_parser/models/ast_model.py`, and the transformer mixins still raise errors without any parser-package logging surface, while `read_text_with_fallback`, `parse_source_text`, and the transformer entrypoint already centralize most exception escape paths.
- [ ] Add a module-level logging surface to the parser API and log the highest-signal failure paths there.
- [ ] Add targeted logging only where model or transformer code would otherwise lose essential context.
- [ ] Add focused parser tests with log capture and rerun strict syntax-check plus narrow pytest.

## Surprises & Discoveries

Observation: most parser failures already pass through a small number of API boundaries.
Evidence: `src/sattline_parser/api.py` owns `read_text_with_fallback`, `load_source_text`, `parse_source_text`, and `parse_source_file`, which is where decode, parse, and transform failures naturally surface.

Observation: the transformer layer contains many direct `ValueError` sites.
Evidence: the mixins under `src/sattline_parser/transformer/` raise many `ValueError` exceptions directly, so logging every raise site would create noise and duplicated messages.

Observation: parser work must preserve strict behavior.
Evidence: repository parser instructions explicitly forbid silent fallback in `sattlint syntax-check`, and the parser package currently raises directly when it cannot decode, parse, or transform.

## Decision Log

Decision: centralize logging in `src/sattline_parser/api.py` first.
Rationale: that file is the narrowest boundary where file path, source text, parse stage, and escaping exception are visible together.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: add targeted logs in model or transformer code only when the API boundary would otherwise lose key context.
Rationale: blanket logging in every `ValueError` site would create duplicate noise without improving diagnostics.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: preserve the exact strict-failure contract of `syntax-check` while adding observability.
Rationale: this debt item is about diagnostics and logging, not about accepting invalid files more leniently.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The current parser already centralizes most failure paths, which makes this debt item smaller than adding logging across the entire parser stack.

## Context and Orientation

The parser API lives in `src/sattline_parser/api.py`. `read_text_with_fallback` handles file decoding, `load_source_text` loads and preprocesses source, `parse_source_text` strips comments, calls the Lark parser, runs `SLTransformer`, and attaches the parse tree when possible, and `describe_parse_error` already formats human-readable parse failures. That file is the first place to add structured logging.

The model coercion layer lives in `src/sattline_parser/models/ast_model.py`, and the transformer mixins live under `src/sattline_parser/transformer/`. Those files already raise structured exceptions when AST shapes are wrong, but they currently do not emit logs. Only add logging there if the API layer cannot infer enough context from the escaping exception.

Parser invariants still apply. Minimal fixtures need three header `STRING` lines before `BasePicture`, `syntax-check` remains stricter than workspace loading, and no change in this plan may introduce silent fallback behavior.

## Plan of Work

Start by adding a module-level logger in `src/sattline_parser/api.py`. Log decode failures in `read_text_with_fallback` or the file-loading path, parse failures in the Lark parse call, and transform failures around `SLTransformer.transform`. Use structured fields such as file path, parser stage, and line or column when the exception exposes them.

Then review `src/sattline_parser/models/ast_model.py` and the transformer package for the few cases where the API layer cannot supply enough context. Only add targeted logs in those places if the escaping exception loses important information such as the offending datatype token or node shape. Keep those logs additive; do not swallow or downgrade the exceptions.

Finally, add focused tests that capture log output with `caplog` while preserving the existing exception or strict-validation behavior. The test should prove both halves of the requirement: logs now exist, and parser strictness has not changed.

## Concrete Steps

Run all commands from the repository root.

Inspect the current parser API and direct raise sites before editing code:

    rg -n "read_text_with_fallback|load_source_text|parse_source_text|describe_parse_error" src/sattline_parser/api.py
    rg -n "raise ValueError|raise RuntimeError|except" src/sattline_parser/models/ast_model.py src/sattline_parser/transformer

After adding logging, run the strict parser validation first:

    python scripts/run_repo_python.py -m sattlint syntax-check tests/fixtures/corpus/valid/VariableModifiers.s

Then run the narrow pytest slice with log-capture coverage:

    python scripts/run_repo_python.py -m pytest --no-cov tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_transformer.py -x -q --tb=short

Run touched-file quality gates after the focused checks pass:

    python scripts/run_repo_python.py -m ruff check src/sattline_parser/api.py src/sattline_parser/models/ast_model.py src/sattline_parser/transformer tests/parser/test_parser_core.py tests/parser/test_parser_validation.py tests/parser/test_transformer.py
    python scripts/run_repo_python.py -m pyright src/sattline_parser/api.py src/sattline_parser/models/ast_model.py src/sattline_parser/transformer

## Validation and Acceptance

Acceptance requires log capture for at least one decode or parse failure and one transform-shape failure, without changing the existing strict exception behavior. `sattlint syntax-check` must still pass on a known-valid corpus file and must still fail strictly on invalid input. The new logs must add context, not replace the current error contract.

## Idempotence and Recovery

This plan is safe to land in two slices. Add the API-boundary logging first and validate it. Only then add any targeted model or transformer logs that are still justified by missing context. If a new log path changes exception behavior or introduces silent fallback, revert that local slice immediately and restore the strict path before continuing.

## Artifacts and Notes

Record one short `caplog` assertion example and one strict `syntax-check` transcript. The important proof is that the parser now logs useful failure context while still failing in exactly the same places.

## Interfaces and Dependencies

The implementation surface is `src/sattline_parser/api.py`, `src/sattline_parser/models/ast_model.py`, and the mixins under `src/sattline_parser/transformer/`. Use the standard library `logging` module. Do not add fallback parsing, best-effort recovery, or any dependency that changes strict parser behavior.
