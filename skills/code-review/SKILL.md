---
name: code-review
description: Review code for bugs, security issues, performance problems, and style. Use when reviewing PRs, auditing code quality, or before deploying changes.
---

# Code Review

Review code changes systematically. Check in this order:

## 1. Security
- Input validation on all user-facing endpoints
- No hardcoded credentials, API keys, or secrets
- SQL injection, XSS, command injection vectors
- Auth/authz checks on protected routes
- Sensitive data not logged or exposed in errors

## 2. Correctness
- Edge cases: empty inputs, null values, off-by-one errors
- Error handling: what happens when external calls fail?
- Race conditions in async code
- Resource cleanup (file handles, connections, streams)

## 3. Performance
- N+1 query patterns
- Unnecessary re-renders or recomputation
- Large payloads being loaded into memory
- Missing indexes on queried fields

## 4. Maintainability
- Functions doing more than one thing
- Magic numbers without explanation
- Dead code or unused imports
- Missing error context in exceptions

## Output format
For each finding:
- **File:line** — what's wrong
- **Severity** — critical / warning / nit
- **Fix** — specific change, not vague advice
