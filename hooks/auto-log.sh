#!/bin/bash
# ToolMaster Auto-Logger Hook
# Fires on Claude Code session Stop event
# Captures what happened in the session and writes to data/logs/
#
# The hook receives context via environment variables:
#   $CLAUDE_PROJECT_DIR — the project directory

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOGS_DIR="$PROJECT_DIR/data/logs"

# Only log for projects under Documents/claude/
case "$PROJECT_DIR" in
  *Documents/claude/*)
    ;;
  *)
    exit 0
    ;;
esac

# Skip ToolMaster itself (it's the observer, not the observed)
case "$PROJECT_DIR" in
  *ToolMaster*)
    exit 0
    ;;
esac

# Create logs dir if it doesn't exist
mkdir -p "$LOGS_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
PROJECT_NAME=$(basename "$PROJECT_DIR")
LOG_ID="auto_$(date +%s)"

# Capture git activity as a proxy for what happened
CHANGED_FILES=""
if [ -d "$PROJECT_DIR/.git" ]; then
  CHANGED_FILES=$(cd "$PROJECT_DIR" && git diff --name-only HEAD 2>/dev/null | head -20)
fi

# Count modified files in last 10 minutes as activity signal
RECENT_FILES=$(find "$PROJECT_DIR" -maxdepth 3 -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.md" -o -name "*.json" 2>/dev/null | xargs stat -f "%m %N" 2>/dev/null | awk -v cutoff=$(($(date +%s) - 600)) '$1 > cutoff {print $2}' | head -20)

# Build the log
cat > "$LOGS_DIR/${LOG_ID}.json" << ENDLOG
{
  "business_name": "${PROJECT_NAME}",
  "client_type": "general",
  "loadout": "none",
  "deliverables_generated": ["session-activity"],
  "sections": {
    "session-activity": {
      "raw_output": "Auto-logged session in ${PROJECT_NAME}",
      "final_output": null,
      "status": "pending",
      "reviewed_at": null
    }
  },
  "generated_at": "${TIMESTAMP}",
  "generation_time_seconds": null,
  "client_rating": null,
  "owner_notes": "Auto-captured by ToolMaster hook. Changed files: ${CHANGED_FILES:-none detected}. Recent activity: $(echo "$RECENT_FILES" | wc -l | tr -d ' ') files modified in last 10min.",
  "_auto_logged": true,
  "_changed_files": "$(echo "$CHANGED_FILES" | tr '\n' ', ')",
  "_recent_files": "$(echo "$RECENT_FILES" | tr '\n' ', ')"
}
ENDLOG

exit 0
