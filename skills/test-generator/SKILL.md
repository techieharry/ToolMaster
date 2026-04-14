---
name: test-generator
description: Generate tests for existing code — unit, integration, edge cases. Use when adding test coverage, verifying fixes, or testing new features.
---

# Test Generator

## What to test
1. **Happy path** — normal input produces expected output
2. **Edge cases** — empty, null, zero, max values, unicode, special chars
3. **Error paths** — invalid input, missing dependencies, network failures
4. **Boundary conditions** — off-by-one, pagination limits, timeout thresholds

## What NOT to test
- Implementation details (private methods, internal state)
- Framework code (don't test that React renders a div)
- Trivial getters/setters with no logic

## Structure per test
```
# Arrange — set up the inputs and dependencies
# Act — call the function/endpoint
# Assert — check the result matches expectations
```

## Rules
- Test names describe the behavior: `test_returns_empty_list_when_no_results`
- One assertion per test (or one logical assertion group)
- Tests must be independent — no shared mutable state between tests
- Mock external services, not internal code
- If you need more than 5 lines of setup, the code is too coupled

## Output
For each function/endpoint:
- 2-3 happy path tests
- 2-3 edge case tests
- 1-2 error path tests
- Each test with clear name, arrange/act/assert, and brief comment on what it verifies
