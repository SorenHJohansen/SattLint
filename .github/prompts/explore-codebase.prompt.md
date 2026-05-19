---
description: "Explore SattLint code paths before editing"
name: "Explore Codebase"
argument-hint: "Symbol, owner surface, or behavior to explore"
agent: "Planner"
---

# Explore Codebase

Explore the requested SattLint code path before any edit recommendation.

Requirements:

- Use grep_search, file_search, semantic_search, and targeted read_file calls for exploration.
- Return the controlling file or symbol, the nearby call flow or owner surface that matters, and the smallest next file or test to inspect.
