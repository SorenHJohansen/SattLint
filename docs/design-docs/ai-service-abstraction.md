# AI Service Abstraction

Status: Proposed
Owner: Devtools AI

## Problem

The AI tooling family currently duplicates prompt rendering, model invocation, retry behavior, and response parsing across separate commands and helpers. That makes capability additions expensive and pushes shared failure handling into repeated local code instead of one enforced contract.

## Goal

Define a shared `AiService` abstraction for devtools AI commands so tool-specific modules can focus on their strategy and artifact handling rather than reimplementing the transport lifecycle.

## Design Task

1. Introduce a base protocol or abstract class under `src/sattlint/devtools/ai/` for prompt rendering, model calls, retry policy, response parsing, and structured error reporting.
2. Define a typed request and response model that carries common configuration such as model name, timeout, retry budget, and output metadata.
3. Refactor AI commands to provide strategy-specific prompt builders and response interpreters while delegating the shared call lifecycle to the new abstraction.
4. Add focused tests that cover retry behavior, parse failures, and artifact emission through the shared abstraction.

## Acceptance Criteria

- Shared AI call lifecycle code lives in one base seam rather than being copied across commands.
- Tool-specific modules expose only strategy differences such as prompt inputs, output schema, and post-processing.
- Retry and parse-failure behavior are unit-tested through the common abstraction.
- Existing CLI and artifact outputs remain backward compatible unless a dedicated migration task is approved.

## Non-Goals

- Picking a single external model provider for all future work.
- Redesigning every AI command in one PR.
- Collapsing unrelated AI command business logic into one module.
