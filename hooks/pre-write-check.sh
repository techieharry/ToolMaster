#!/bin/bash
# ToolMaster Pre-Write Check Hook
# Fires BEFORE Write/Edit tool calls
# Checks if the agent has checked in and checked out
# Outputs a warning (not a block) if they haven't

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Only run for projects under Documents/claude/
case "$PROJECT_DIR" in
  *Documents/claude/*) ;;
  *) exit 0 ;;
esac

case "$PROJECT_DIR" in
  *ToolMaster*) exit 0 ;;
esac

SESSION_FILE="$PROJECT_DIR/data/toolmaster_session.json"

# Check if session exists
if [ ! -f "$SESSION_FILE" ]; then
  echo "[TOOLMASTER] WARNING: No active session. Run: python3 -m toolmaster checkin"
  exit 0
fi

# Check if the file being written is a SKILL.md
TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"
if echo "$TOOL_INPUT" | grep -q "SKILL.md"; then
  # Check if agent ran checkout before creating a skill
  CHECKOUTS=$(python3 -c "
import json
m = json.load(open('$SESSION_FILE'))
checks = m.get('session', {}).get('tools_checked', [])
print(len(checks))
" 2>/dev/null)

  if [ "$CHECKOUTS" = "0" ]; then
    echo "[TOOLMASTER] WARNING: Creating a SKILL.md without checking the toolbox first."
    echo "  Run: python3 -m toolmaster checkout \"describe what this skill does\""
    echo "  A similar tool may already exist in the global toolbox."
  fi
fi

exit 0
