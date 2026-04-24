---
name: concurrent-work
description: 'Coordinate parallel SattLint work across multiple chats or agents. Use for claiming files, writing handoff notes, tracking validations, and avoiding edit collisions in `.github/coordination/current-work.md`.'
argument-hint: 'Task, owner, and files to claim'
---

# Concurrent Work

Use this skill when several chats or agents are active in SattLint at same time.

## Goals

- Keep one shared ledger of active work.
- Avoid two workstreams editing same file by accident.
- Make handoffs and validation status visible before merge or review.

## Procedure

1. Read `.github/coordination/current-work.md` before first edit.
2. Add or update one row for current workstream using [workstream template](./assets/workstream-template.md).
3. Claim exact files or directories before editing.
4. Record one first validation command that fits touched surface.
5. When scope changes, update claims before touching new files.
6. On completion, mark status, add handoff notes, and release claims.

## Claim Rules

- Prefer exact files over broad directories.
- If a shared file is unavoidable, note merge owner and expected edit window.
- Use `blocked` status when another stream already owns controlling file.
- Keep notes terse and factual.

## Guard Behavior

- Active claims trigger a hook warning before edit tools run.
- `ready-for-merge` claims escalate to confirmation.
- `blocked` claims deny edit-tool execution until the ledger changes.
- Edits to `.github/coordination/current-work.md` stay allowed so claims can be updated.

## Suggested Status Values

- `planned`
- `active`
- `blocked`
- `ready-for-merge`
- `done`

## Required Fields Per Entry

- workstream id
- owner
- goal
- claimed files
- first validation command
- status
- handoff or blocker note
