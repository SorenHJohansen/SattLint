---
description: Review SattLint changes without editing
agent: sattlint-reviewer
---

Review `$ARGUMENTS`. If the argument is empty, review the uncommitted changes
and the current branch diff against `main`.

Report findings in severity order with `file:line` references. Do not edit files.

Check:

1. Analyzer behavior, including references or writes that became invisible.
2. Parser boundary, import doors, and the exact parser pin.
3. Test evidence from real parser output.
4. Cache version when AST semantics or graphics attachments changed.
5. Changelog and matching instruction docs.
6. Public repository wording and dash punctuation.

If something is clean, say so. If a check cannot be run, say what is missing.
