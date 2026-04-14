#!/bin/bash
# ToolMaster Auto-Checkin Hook
# Fires on Claude Code session start (Notification event)
# Auto-checks in, shows toolbox state, injects context

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
TOOLMASTER_DIR="$HOME/Documents/claude/ToolMaster"

# Only run for projects under Documents/claude/
case "$PROJECT_DIR" in
  *Documents/claude/*) ;;
  *) exit 0 ;;
esac

# Skip ToolMaster itself
case "$PROJECT_DIR" in
  *ToolMaster*) exit 0 ;;
esac

# Auto-checkin
cd "$TOOLMASTER_DIR" 2>/dev/null || exit 0
CHECKIN=$(python3 -m toolmaster checkin --project "$PROJECT_DIR" 2>&1)

# Output gets shown to the agent as hook feedback
echo "=== TOOLMASTER AUTO-CHECKIN ==="
echo "$CHECKIN"
echo ""
echo "REMINDER: Before building anything from scratch, run:"
echo "  python3 -m toolmaster checkout \"describe your task\""
echo "=== END TOOLMASTER ==="
