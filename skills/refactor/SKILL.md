---
name: refactor
description: Refactor code for clarity, maintainability, and performance. Use when simplifying complex functions, extracting patterns, or reducing duplication.
---

# Refactor

## When to refactor
- Function is over 50 lines
- Same pattern appears 3+ times
- You need a comment to explain what code does (the code should say it)
- Changing one thing requires changing many files
- Tests are hard to write for this code

## Process
1. **Ensure tests exist** — never refactor without a safety net
2. **Identify the smell** — name what's wrong (duplication, coupling, complexity)
3. **Apply one transformation** — extract function, rename, inline, split
4. **Run tests** — verify nothing broke
5. **Repeat** — one small change at a time, never big-bang refactor

## Common refactors
- **Extract function** — pull a named chunk out of a long function
- **Rename** — make names match what code actually does
- **Inline** — remove unnecessary abstraction that adds indirection without value
- **Split module** — break a file doing 3 things into 3 files doing 1 thing each
- **Replace conditional with polymorphism** — when if/else chains map to types

## Rules
- Refactor OR add features. Never both in the same commit.
- The behavior must not change. Refactoring is restructuring, not rewriting.
- If you're not sure the tests cover it, don't refactor it.
- Three similar lines is better than a premature abstraction.
