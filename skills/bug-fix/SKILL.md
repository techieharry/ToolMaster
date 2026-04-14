---
name: bug-fix
description: Systematic bug diagnosis and fix. Use when debugging errors, unexpected behavior, or failing tests. Follows root-cause-first approach.
---

# Bug Fix

## Process
1. **Reproduce** — confirm the bug exists, get exact error/behavior
2. **Isolate** — narrow to the smallest code path that triggers it
3. **Root cause** — find the actual cause, not just the symptom
4. **Fix** — change the minimum code needed
5. **Verify** — confirm the fix works AND doesn't break anything else

## Rules
- Never fix symptoms. If a null check "fixes" a crash, find why it's null.
- Read the error message. The answer is usually in the stack trace.
- Check git blame — when was this code last changed and by whom?
- One fix per bug. Don't refactor while fixing.
- Add a test that would have caught this bug.

## Output
- **Root cause**: one sentence explaining why the bug exists
- **Fix**: the minimal code change
- **Test**: how to verify the fix
- **Prevention**: what would catch this class of bug in the future
