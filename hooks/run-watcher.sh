#!/bin/bash
# ToolMaster Global Watcher — persistent background process
# Polls all projects every 30s, writes to log file.
#
# Start:   hooks/run-watcher.sh start
# Stop:    hooks/run-watcher.sh stop
# Status:  hooks/run-watcher.sh status
# Restart: hooks/run-watcher.sh restart
#
# Config (read from env, optionally sourced from <repo>/.env):
#   OPENROUTER_API_KEY   required for scout layer (GitHub audit + re-engineer)
#   CLAUDE_DIR           root of your projects tree (default: C:/Claude)
#   TOOLMASTER_HOME      watcher state dir (default: ~/.toolmaster)

# Self-locate the repo so this script works regardless of cwd or user layout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLMASTER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load <repo>/.env if present (untracked, holds secrets).
if [ -f "$TOOLMASTER_DIR/.env" ]; then
    set -a
    . "$TOOLMASTER_DIR/.env"
    set +a
fi

STATE_DIR="${TOOLMASTER_HOME:-$HOME/.toolmaster}"
PIDFILE="$STATE_DIR/watcher.pid"
LOGFILE="$STATE_DIR/watcher.log"

mkdir -p "$STATE_DIR"

start() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Watcher already running (PID $(cat "$PIDFILE"))"
        return
    fi

    if [ -z "$OPENROUTER_API_KEY" ]; then
        echo "WARNING: OPENROUTER_API_KEY is not set — scout layer will be inert."
        echo "         Set it in $TOOLMASTER_DIR/.env or export it before starting."
    fi

    cd "$TOOLMASTER_DIR" || { echo "Cannot cd to $TOOLMASTER_DIR"; exit 1; }
    PYTHONUNBUFFERED=1 nohup python3 -m toolmaster watch --interval 30 >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "Watcher started (PID $!)"
    echo "Repo:  $TOOLMASTER_DIR"
    echo "State: $STATE_DIR"
    echo "Log:   $LOGFILE"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PIDFILE"
            echo "Watcher stopped (PID $PID)"
        else
            rm -f "$PIDFILE"
            echo "Watcher was not running (stale PID)"
        fi
    else
        echo "Watcher is not running"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Watcher running (PID $(cat "$PIDFILE"))"
        echo "Log: $LOGFILE"
        echo ""
        echo "Last 10 lines:"
        tail -10 "$LOGFILE"
        echo ""
        cd "$TOOLMASTER_DIR" && python3 -m toolmaster watch --status
    else
        echo "Watcher is not running"
    fi
}

case "${1:-start}" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
    restart) stop; sleep 1; start ;;
    *)      echo "Usage: $0 {start|stop|status|restart}" ;;
esac
