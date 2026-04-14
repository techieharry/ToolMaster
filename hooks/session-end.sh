#!/bin/bash
# ToolMaster Auto-Return Hook
# Fires on Claude Code session Stop
# Auto-returns tools, archives session, scores compliance, logs activity

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

cd "$TOOLMASTER_DIR" 2>/dev/null || exit 0

# Check if there's an active session to return
SESSION_FILE="$PROJECT_DIR/data/toolmaster_session.json"
if [ -f "$SESSION_FILE" ]; then
  STATUS=$(python3 -c "import json; print(json.load(open('$SESSION_FILE')).get('status','unknown'))" 2>/dev/null)
  if [ "$STATUS" = "active" ]; then
    # Auto-return
    python3 -m toolmaster return --project "$PROJECT_DIR" 2>/dev/null
  fi
fi

# Also run the auto-log (capture file changes as thin log)
LOGS_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
PROJECT_NAME=$(basename "$PROJECT_DIR")
LOG_ID="auto_$(date +%s)"

# Capture git changes
CHANGED_FILES=""
if [ -d "$PROJECT_DIR/.git" ]; then
  CHANGED_FILES=$(cd "$PROJECT_DIR" && git diff --name-only HEAD 2>/dev/null | head -20)
fi

# Capture recent file modifications
RECENT_COUNT=$(find "$PROJECT_DIR" -maxdepth 3 \( -name "*.py" -o -name "*.ts" -o -name "*.js" -o -name "*.md" -o -name "*.json" \) -newer "$PROJECT_DIR/data/toolmaster_session.json" 2>/dev/null | wc -l | tr -d ' ')

# Check if any SKILL.md files were created/modified this session
NEW_SKILLS=$(find "$PROJECT_DIR" -maxdepth 4 -name "SKILL.md" -newer "$PROJECT_DIR/data/toolmaster_session.json" 2>/dev/null)

# Read compliance from session if available
COMPLIANCE="unknown"
if [ -f "$SESSION_FILE" ]; then
  COMPLIANCE=$(python3 -c "
import json
m = json.load(open('$SESSION_FILE'))
s = m.get('summary', {})
print(f\"{s.get('checked_before_building', 'N/A')}\")
" 2>/dev/null)
fi

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
  "owner_notes": "Auto-captured. Files modified: ${RECENT_COUNT}. Compliance: ${COMPLIANCE}. New skills detected: $(echo "$NEW_SKILLS" | wc -l | tr -d ' '). Changed: ${CHANGED_FILES:-none}",
  "_auto_logged": true,
  "_compliance": "${COMPLIANCE}",
  "_new_skills_detected": $([ -n "$NEW_SKILLS" ] && echo "true" || echo "false"),
  "_files_modified": ${RECENT_COUNT}
}
ENDLOG

exit 0
