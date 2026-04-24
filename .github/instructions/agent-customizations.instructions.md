---
description: "Use when changing AGENTS, custom agents, prompts, skills, hooks, or other repo AI customizations in SattLint. Covers discoverability, context efficiency, and hook safety rules."
name: "Agent Customization Instructions"
applyTo: ["AGENTS.md", ".github/agents/**", ".github/prompts/**", ".github/skills/**", ".github/hooks/**"]
---
# Agent Customizations

- Prefer scoped instructions over growing global instructions.
- Keep frontmatter concise and keyword-rich so discovery works.
- Avoid broad `applyTo` unless the instruction truly applies everywhere.
- Hook scripts must fail open unless blocking behavior is explicitly intended and safe.
- Validate hook scripts with a compile or smoke test, and validate markdown or JSON files with workspace diagnostics.